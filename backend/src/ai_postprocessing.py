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
import os
import yaml
from typing import Dict, Optional, Tuple
from shared_quickscribe_py.cosmos import get_recording_handler, get_transcription_handler, get_participant_handler, Recording, Transcription
from llms import (
    send_multiple_prompts_concurrent,
    get_speaker_mapping,
    send_prompt_to_llm
)

# Load prompts
_script_dir = os.path.dirname(os.path.abspath(__file__))
_prompts_path = os.path.join(_script_dir, '..', 'prompts.yaml')

with open(_prompts_path, 'r') as stream:
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


def update_speaker_names(transcription_id: str, transcript_text: str, recording_id: str, recording: 'Recording' = None, transcription: 'Transcription' = None) -> Optional[Dict]:
    """
    Enhanced speaker inference with participant linking.
    Uses existing LLM speaker inference then suggests/creates participant profiles.
    
    Args:
        transcription_id: ID of the transcription to update
        transcript_text: The diarized transcript text
        recording_id: ID of the recording to update with participants
        recording: Optional recording object (to avoid refetching)
        transcription: Optional transcription object (to avoid refetching)
        
    Returns:
        Dict with speaker mapping results or None if failed
    """
    try:
        # Get user ID for participant operations
        if not recording:
            recording_handler = get_recording_handler()
            recording = recording_handler.get_recording(recording_id)
            if not recording:
                logger.error(f"Recording {recording_id} not found")
                return None
        
        user_id = recording.user_id
        
        # Use existing speaker inference functionality
        raw_speaker_mapping, updated_transcript = get_speaker_mapping(transcript_text)
        
        # Get participant suggestions/creations based on speaker names
        participant_suggestions = suggest_participants_for_speakers(user_id, raw_speaker_mapping)
        
        # Convert raw dictionary to enhanced SpeakerMapping objects with participant info
        from shared_quickscribe_py.cosmos.models import SpeakerMapping
        formatted_speaker_mapping = {}
        recording_participants = []
        
        for speaker_id, speaker_data in raw_speaker_mapping.items():
            # Get participant info for this speaker
            participant_info = participant_suggestions.get(speaker_id, {})
            
            # Create normalized SpeakerMapping (no denormalized name/displayName/reasoning)
            formatted_speaker_mapping[speaker_id] = SpeakerMapping(
                participantId=participant_info.get("participantId"),
                confidence=participant_info.get("confidence"),
                manuallyVerified=participant_info.get("manuallyVerified", False)
            )
            
            # Create RecordingParticipant entry if we have a valid participant
            if participant_info.get("participantId"):
                from shared_quickscribe_py.cosmos.models import RecordingParticipant
                recording_participants.append(RecordingParticipant(
                    participantId=participant_info["participantId"],
                    displayName=participant_info["displayName"],
                    speakerLabel=speaker_id,
                    confidence=participant_info["confidence"],
                    manuallyVerified=participant_info["manuallyVerified"]
                ))
        
        logger.info(f"Enhanced speaker mapping for {len(formatted_speaker_mapping)} speakers with {len(recording_participants)} participant links")
        
        # Update the transcription with enhanced speaker mapping
        transcription_handler = get_transcription_handler()
        if not transcription:
            transcription = transcription_handler.get_transcription(transcription_id)
        
        if transcription:
            transcription.speaker_mapping = formatted_speaker_mapping
            transcription_handler.update_transcription(transcription)

            # Note: We no longer store participants on recordings - only in transcription.speaker_mapping

            # Extract participant names for backward compatibility in response
            participant_names = [p.displayName for p in recording_participants]
            if not participant_names:
                # Fallback to speaker names if no participants linked
                participant_names = [speaker_data["name"] for speaker_data in raw_speaker_mapping.values()]
            
            logger.info(f"Updated speaker names for transcription {transcription_id}")
            return {
                'speaker_mapping': formatted_speaker_mapping,
                'participants': participant_names,
                'recording_participants': recording_participants,
                'participant_suggestions': participant_suggestions
            }
    except Exception as e:
        logger.warning(f"Speaker inference failed for transcription {transcription_id}: {e}")
        return None


def suggest_participants_for_speakers(user_id: str, speaker_mapping: Dict) -> Dict:
    """
    Suggest existing participants for speaker names and auto-create profiles for new speakers.
    
    Args:
        user_id: ID of the user
        speaker_mapping: Dictionary of speaker labels to speaker data
        
    Returns:
        Dictionary mapping speaker labels to participant info
    """
    try:
        participant_handler = get_participant_handler()
        suggestions = {}
        
        for speaker_label, speaker_data in speaker_mapping.items():
            speaker_name = speaker_data.get("name", "").strip()
            
            # Skip generic speaker names
            if not speaker_name or speaker_name.lower().startswith("speaker "):
                continue
            
            # Search for existing participants
            existing_participants = participant_handler.find_participants_by_name(
                user_id, speaker_name, fuzzy=True
            )
            
            if existing_participants:
                # Use the best match (first result from search)
                best_match = existing_participants[0]
                confidence = 1.0 if speaker_name.lower() == best_match.displayName.lower() else 0.8
                
                suggestions[speaker_label] = {
                    "participantId": best_match.id,
                    "displayName": best_match.displayName,
                    "confidence": confidence,
                    "manuallyVerified": False,
                    "matched_existing": True
                }
                
                # Update last seen for existing participant
                participant_handler.update_participant_last_seen(user_id, best_match.id)
                
                logger.info(f"Matched speaker '{speaker_name}' to existing participant '{best_match.displayName}' (confidence: {confidence})")
                
            else:
                # Create new participant profile
                try:
                    # Parse name into firstName/lastName if possible
                    name_parts = speaker_name.split()
                    firstName = name_parts[0] if name_parts else ""
                    lastName = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
                    
                    new_participant = participant_handler.create_participant(
                        user_id=user_id,
                        displayName=speaker_name,
                        firstName=firstName if firstName else None,
                        lastName=lastName if lastName else None
                    )
                    
                    suggestions[speaker_label] = {
                        "participantId": new_participant.id,
                        "displayName": new_participant.displayName,
                        "confidence": 0.9,  # High confidence for new creation
                        "manuallyVerified": False,
                        "matched_existing": False
                    }
                    
                    logger.info(f"Created new participant '{speaker_name}' for speaker label '{speaker_label}'")
                    
                except Exception as e:
                    logger.error(f"Failed to create participant for speaker '{speaker_name}': {e}")
                    # Continue without participant linkage for this speaker
                    suggestions[speaker_label] = {
                        "participantId": None,
                        "displayName": speaker_name,
                        "confidence": 0.0,
                        "manuallyVerified": False,
                        "matched_existing": False
                    }
        
        return suggestions
        
    except Exception as e:
        logger.error(f"Error suggesting participants for speakers: {e}")
        return {}


def get_transcript_text_for_processing(recording_id: str) -> Tuple[Optional[str], Optional[str], Optional['Transcription']]:
    """
    Get the best available transcript text for AI processing.
    
    Args:
        recording_id: ID of the recording
        
    Returns:
        Tuple of (transcript_text, transcription_id, transcription) or (None, None, None) if not available
    """
    try:
        transcription_handler = get_transcription_handler()
        transcription = transcription_handler.get_transcription_by_recording(recording_id)
        
        if not transcription:
            logger.warning(f"No transcription found for recording {recording_id}")
            return None, None, None
            
        # Prefer diarized transcript, fall back to regular text
        diarized_length = len(transcription.diarized_transcript) if transcription.diarized_transcript else 0
        regular_length = len(transcription.text) if transcription.text else 0
        
        logger.info(f"Transcript data available - diarized: {diarized_length} chars, regular: {regular_length} chars")
        
        transcript_text = transcription.diarized_transcript or transcription.text
        
        if not transcript_text:
            logger.warning(f"No transcript text available for recording {recording_id}")
            return None, None, None
        
        used_type = "diarized" if transcription.diarized_transcript else "regular"
        logger.info(f"Using {used_type} transcript: {len(transcript_text)} characters")
            
        return transcript_text, transcription.id, transcription
        
    except Exception as e:
        logger.error(f"Error getting transcript for recording {recording_id}: {e}")
        return None, None, None


def has_manually_verified_speakers(transcription: 'Transcription') -> bool:
    """
    Check if the transcription has any manually verified speakers.
    
    Args:
        transcription: The transcription object to check
        
    Returns:
        True if any speakers are manually verified, False otherwise
    """
    if not transcription or not transcription.speaker_mapping:
        return False
    
    # Check if any speakers are manually verified
    for speaker_data in transcription.speaker_mapping.values():
        if hasattr(speaker_data, 'manuallyVerified') and speaker_data.manuallyVerified:
            logger.info(f"Found manually verified speaker: {speaker_data}")
            return True
    
    return False


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
            
        transcript_text, transcription_id, transcription = get_transcript_text_for_processing(recording_id)
        
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
        
        # Speaker inference disabled - users will manually assign speakers
        logger.info(f"Speaker inference disabled for recording {recording_id}")
        results['speaker_update'] = {'skipped': 'feature_disabled'}
        
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


def update_transcription_speaker_data_with_participants(transcription_id: str, speaker_mapping: dict, reasoning: str = "User edited") -> dict:
    """
    Update transcription speaker mapping with participant data.

    Args:
        transcription_id: ID of the transcription to update
        speaker_mapping: Dict of speaker label -> participant data
        reasoning: Unused, kept for backward compatibility

    Returns:
        Results dict with update status
    """
    from shared_quickscribe_py.cosmos.models import SpeakerMapping

    transcription_handler = get_transcription_handler()
    transcription = transcription_handler.get_transcription(transcription_id)

    if not transcription:
        return {'error': f'Transcription {transcription_id} not found'}

    # Update speaker mapping with normalized data (no denormalized name/displayName/reasoning)
    updated_mapping = {}
    for speaker_label, participant_data in speaker_mapping.items():
        if isinstance(participant_data, dict):
            participant_id = participant_data.get('participantId')

            # Create normalized SpeakerMapping
            speaker_mapping_obj = SpeakerMapping(
                participantId=participant_id,
                confidence=1.0,
                manuallyVerified=True
            )
            updated_mapping[speaker_label] = speaker_mapping_obj

    if updated_mapping:
        transcription.speaker_mapping = updated_mapping
        transcription_handler.update_transcription(transcription)
        logger.info(f"Updated transcription {transcription_id} speaker mapping with participant links")

    return {'success': True, 'updated_speakers': len(updated_mapping)}


def update_recording_participants(recording_id: str, participants: list[str]) -> None:
    """
    DEPRECATED: Recording participants are no longer used.
    Speaker mappings are stored only in transcription.speaker_mapping.
    This function is kept for backward compatibility but does nothing.
    """
    logger.warning(f"update_recording_participants called for {recording_id} but is deprecated - no action taken")


def update_recording_participants_with_participants(recording_id: str, speaker_mapping: dict) -> None:
    """
    DEPRECATED: Recording participants are no longer used.
    Speaker mappings are stored only in transcription.speaker_mapping.
    This function is kept for backward compatibility but does nothing.
    """
    logger.warning(f"update_recording_participants_with_participants called for {recording_id} but is deprecated - no action taken")


def update_diarized_transcript_with_names(diarized_transcript: str, speaker_mapping: dict) -> str:
    """
    Update diarized transcript by replacing speaker labels with actual names.
    
    Args:
        diarized_transcript: Original transcript with Speaker 1, Speaker 2, etc.
        speaker_mapping: Dict mapping speaker labels to names
        
    Returns:
        Updated transcript with real names
    """
    updated_transcript = diarized_transcript
    for speaker_label, speaker_name in speaker_mapping.items():
        updated_transcript = updated_transcript.replace(f"{speaker_label}:", f"{speaker_name}:")
    return updated_transcript


def update_transcription_speaker_data(transcription_id: str, speaker_mapping: dict, reasoning: str = "User edited") -> dict:
    """
    Update transcription with new speaker mapping (legacy format - names only).

    DEPRECATED: Use update_transcription_speaker_data_with_participants instead.
    This function stores speaker mappings without participant links.

    Args:
        transcription_id: ID of transcription to update
        speaker_mapping: Dict mapping speaker labels to names (legacy format)
        reasoning: Unused, kept for backward compatibility

    Returns:
        Dict with updated speaker mapping and transcript
    """
    from shared_quickscribe_py.cosmos.models import SpeakerMapping

    logger.warning(f"Using deprecated update_transcription_speaker_data for {transcription_id}. "
                   "Speaker names without participant links will not be stored.")

    transcription_handler = get_transcription_handler()
    transcription = transcription_handler.get_transcription(transcription_id)

    if not transcription:
        raise ValueError(f"Transcription {transcription_id} not found")

    # Create normalized SpeakerMapping objects (no participantId means no linked participant)
    formatted_speaker_mapping = {}
    for speaker_label, speaker_name in speaker_mapping.items():
        formatted_speaker_mapping[speaker_label] = SpeakerMapping(
            participantId=None,
            confidence=None,
            manuallyVerified=False
        )

    # Update transcription with speaker mapping only - leave diarized transcript unchanged
    transcription.speaker_mapping = formatted_speaker_mapping
    transcription_handler.update_transcription(transcription)

    logger.info(f"Updated transcription {transcription_id} with speaker mapping (no participant links)")

    return {
        'speaker_mapping': {k: v.model_dump() for k, v in formatted_speaker_mapping.items()},
        'participants': list(speaker_mapping.values())
    }