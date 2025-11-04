from flask import Blueprint, jsonify, request
from shared_quickscribe_py.cosmos import get_transcription_handler, get_analysis_type_handler
from llms import get_speaker_summaries_via_llm, get_speaker_mapping
from logging_config import get_logger
from api_version import API_VERSION
from user_util import get_current_user, require_auth
from pydantic import ValidationError
from shared_quickscribe_py.cosmos import (
    CreateAnalysisTypeRequest,
    ExecuteAnalysisRequest,
    UpdateAnalysisTypeRequest,
    AnalysisResult
)
from datetime import datetime, UTC
import uuid

# Initialize logger
logger = get_logger('ai_routes', API_VERSION)

ai_bp = Blueprint('ai', __name__)

@ai_bp.route('/test', methods=['GET'])
def test():
    return jsonify({"status": "up"})

@ai_bp.route('/get_speaker_summaries/<transcription_id>', methods=['GET'])
def get_speaker_summaries(transcription_id):
    logger.info(f"get_speaker_summaries: transcription_id {transcription_id}")
    transcription_handler = get_transcription_handler()
    transcription = transcription_handler.get_transcription(transcription_id)
    if transcription and transcription.diarized_transcript:
        logger.info(f"get_speaker_summaries: found diarized transcript")
        
        # Process transcript line by line to create sequential speaker mapping
        lines = transcription.diarized_transcript.split('\n')
        speaker_mapping = {}  # original_name -> Speaker X
        speaker_counter = 1
        normalized_transcript_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check if line starts with a speaker pattern (name followed by colon)
            speaker_match = line.split(':', 1)
            if len(speaker_match) == 2:
                original_speaker = speaker_match[0].strip()
                content = speaker_match[1].strip()
                
                # If this is a new speaker, assign them the next number
                if original_speaker not in speaker_mapping:
                    speaker_mapping[original_speaker] = f"Speaker {speaker_counter}"
                    speaker_counter += 1
                
                # Add normalized line
                normalized_transcript_lines.append(f"{speaker_mapping[original_speaker]}: {content}")
            else:
                # Non-speaker line, add as-is
                normalized_transcript_lines.append(line)
        
        # Create normalized transcript with Speaker 1, Speaker 2, etc.
        normalized_transcript = '\n'.join(normalized_transcript_lines)
        
        logger.info(f"get_speaker_summaries: speaker_mapping {speaker_mapping}")
        logger.info(f"get_speaker_summaries: normalized transcript preview: {normalized_transcript[:200]}...")
        
        # Get summaries from LLM using normalized transcript
        summaries = get_speaker_summaries_via_llm(normalized_transcript)
        logger.info(f"get_speaker_summaries: LLM returned summaries {summaries}")
        
        # Return summaries with Speaker 1, Speaker 2, etc. keys
        return jsonify(summaries), 200
    return jsonify({'error': 'Transcription not found or does not have a diarized transcript'}), 404

@ai_bp.route('/infer_speaker_names/<transcription_id>')
def infer_speaker_names(transcription_id):
    transcription_handler = get_transcription_handler()
    transcription = transcription_handler.get_transcription(transcription_id)
    if transcription and transcription.diarized_transcript:
        if True: # TODO - uncomment this when we don't want to allow inferring multiple times... not transcription.speaker_mapping:
            speaker_mapping, diarized_text = get_speaker_mapping(transcription.diarized_transcript)
            transcription.speaker_mapping = speaker_mapping
            transcription.diarized_transcript = diarized_text
            transcription_handler.update_transcription(transcription)
            return jsonify({'message': 'Speaker names successfully inferred'}), 200
        else:
            return jsonify({'message': 'Speaker names already inferred'}), 200
    else:
        return jsonify({'error': 'Transcription not found'}), 404


# Analysis Types Management Endpoints

@ai_bp.route('/analysis-types', methods=['GET'])
@require_auth
def get_analysis_types():
    """Get all analysis types available to the current user (built-in + custom)."""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not found'}), 401
            
        analysis_type_handler = get_analysis_type_handler()
        analysis_types = analysis_type_handler.get_analysis_types_for_user(user.id)
        
        # Convert to dictionaries for JSON response
        analysis_types_data = [at.model_dump(exclude_unset=True) for at in analysis_types]
        
        logger.info(f"Retrieved {len(analysis_types)} analysis types for user {user.id}")
        return jsonify({
            'status': 'success',
            'data': analysis_types_data,
            'count': len(analysis_types)
        }), 200
        
    except Exception as e:
        logger.error(f"Error retrieving analysis types: {e}")
        return jsonify({'error': 'Failed to retrieve analysis types'}), 500


@ai_bp.route('/analysis-types', methods=['POST'])
@require_auth
def create_analysis_type():
    """Create a new custom analysis type."""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not found'}), 401
            
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        # Validate request using shared model
        try:
            request_data = CreateAnalysisTypeRequest(**data)
        except ValidationError as e:
            return jsonify({'error': f'Validation error: {str(e)}'}), 400
            
        # Additional business validation
        if len(request_data.shortTitle) > 12:
            return jsonify({'error': 'shortTitle must be 12 characters or less'}), 400
            
        analysis_type_handler = get_analysis_type_handler()
        
        created_type = analysis_type_handler.create_analysis_type(
            name=request_data.name,
            title=request_data.title,
            short_title=request_data.shortTitle,
            description=request_data.description,
            icon=request_data.icon,
            prompt=request_data.prompt,
            user_id=user.id
        )
        
        if not created_type:
            return jsonify({'error': 'Failed to create analysis type'}), 500
            
        logger.info(f"Created custom analysis type '{data['name']}' for user {user.id}")
        return jsonify({
            'status': 'success',
            'data': created_type.model_dump(exclude_unset=True),
            'message': 'Analysis type created successfully'
        }), 201
        
    except ValueError as e:
        logger.warning(f"Validation error creating analysis type: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating analysis type: {e}")
        return jsonify({'error': 'Failed to create analysis type'}), 500


@ai_bp.route('/analysis-types/<type_id>', methods=['PUT'])
@require_auth
def update_analysis_type(type_id):
    """Update a custom analysis type (user can only update their own)."""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not found'}), 401
            
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        analysis_type_handler = get_analysis_type_handler()
        
        # Only allow updating certain fields
        allowed_fields = ['title', 'shortTitle', 'description', 'icon', 'prompt', 'name']
        updates = {k: v for k, v in data.items() if k in allowed_fields and v is not None}
        
        # Validate shortTitle length if provided
        if 'shortTitle' in updates and len(updates['shortTitle']) > 12:
            return jsonify({'error': 'shortTitle must be 12 characters or less'}), 400
        
        if not updates:
            return jsonify({'error': 'No valid fields provided for update'}), 400
            
        updated_type = analysis_type_handler.update_analysis_type(type_id, user.id, updates)
        
        if not updated_type:
            return jsonify({'error': 'Analysis type not found or insufficient permissions'}), 404
            
        logger.info(f"Updated analysis type {type_id} for user {user.id}")
        return jsonify({
            'status': 'success',
            'data': updated_type.model_dump(exclude_unset=True),
            'message': 'Analysis type updated successfully'
        }), 200
        
    except ValueError as e:
        logger.warning(f"Validation error updating analysis type: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating analysis type {type_id}: {e}")
        return jsonify({'error': 'Failed to update analysis type'}), 500


@ai_bp.route('/analysis-types/<type_id>', methods=['DELETE'])
@require_auth
def delete_analysis_type(type_id):
    """Delete a custom analysis type (user can only delete their own)."""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not found'}), 401
            
        analysis_type_handler = get_analysis_type_handler()
        
        success = analysis_type_handler.delete_analysis_type(type_id, user.id)
        
        if not success:
            return jsonify({'error': 'Analysis type not found or insufficient permissions'}), 404
            
        logger.info(f"Deleted analysis type {type_id} for user {user.id}")
        return jsonify({
            'status': 'success',
            'message': 'Analysis type deleted successfully'
        }), 200
        
    except ValueError as e:
        logger.warning(f"Validation error deleting analysis type: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting analysis type {type_id}: {e}")
        return jsonify({'error': 'Failed to delete analysis type'}), 500


@ai_bp.route('/execute-analysis', methods=['POST'])
@require_auth
def execute_analysis():
    """Execute analysis with dynamic type and prompt."""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not found'}), 401
            
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        # Validate request using shared model
        try:
            request_data = ExecuteAnalysisRequest(**data)
        except ValidationError as e:
            return jsonify({'error': f'Validation error: {str(e)}'}), 400
            
        transcription_id = request_data.transcriptionId
        analysis_type_id = request_data.analysisTypeId
        custom_prompt = request_data.customPrompt  # Optional override
        
        # Get transcription
        transcription_handler = get_transcription_handler()
        transcription = transcription_handler.get_transcription(transcription_id)
        
        if not transcription:
            return jsonify({'error': 'Transcription not found'}), 404
            
        # Verify user owns the transcription
        if transcription.user_id != user.id:
            return jsonify({'error': 'Insufficient permissions'}), 403
            
        # Get analysis type
        analysis_type_handler = get_analysis_type_handler()
        
        # Try user partition first, then global
        analysis_type = analysis_type_handler.get_analysis_type_by_id(analysis_type_id, user.id)
        if not analysis_type:
            analysis_type = analysis_type_handler.get_analysis_type_by_id(analysis_type_id, "global")
            
        if not analysis_type:
            return jsonify({'error': 'Analysis type not found'}), 404
            
        # Use custom prompt if provided, otherwise use analysis type's prompt
        prompt_template = custom_prompt or analysis_type.prompt
        
        # Get transcript text for analysis
        transcript_text = transcription.diarized_transcript or transcription.text
        if not transcript_text:
            return jsonify({'error': 'No transcript content available for analysis'}), 400
            
        # Transform transcript to use speaker names if mapping exists
        from shared_quickscribe_py.cosmos import TranscriptionHandler
        transcript_text = TranscriptionHandler.transform_transcript_with_speaker_names(
            transcript_text, 
            transcription.speaker_mapping
        )
        if transcription.speaker_mapping:
            logger.info(f"Transformed transcript for analysis using speaker mapping")
            
        # Replace {transcript} placeholder in prompt template with actual transcript
        final_prompt = prompt_template.replace('{transcript}', transcript_text)
        
        logger.info(f"Executing analysis for transcription {transcription_id} with type {analysis_type.name}")
        
        # Execute LLM analysis with timing
        from llms import send_prompt_to_llm_with_timing
        
        try:
            llm_result = send_prompt_to_llm_with_timing(final_prompt)
            
            # Create analysis result with timing information
            analysis_result = AnalysisResult(
                analysisType=analysis_type.name,
                analysisTypeId=analysis_type_id,
                content=llm_result['content'],
                createdAt=datetime.now(UTC).isoformat(),
                status='completed',
                llmResponseTimeMs=llm_result['llmResponseTimeMs'],
                promptTokens=llm_result['promptTokens'],
                responseTokens=llm_result['responseTokens']
            )
            
            # Add to transcription analysisResults
            if not transcription.analysisResults:
                transcription.analysisResults = []
            transcription.analysisResults.append(analysis_result)
            
            # Save updated transcription
            transcription_handler.update_transcription(transcription)
            
            logger.info(f"Analysis completed for transcription {transcription_id} in {llm_result['llmResponseTimeMs']}ms")
            
            return jsonify({
                'status': 'success',
                'message': 'Analysis completed successfully',
                'data': analysis_result.model_dump()
            }), 200
            
        except Exception as llm_error:
            logger.error(f"LLM analysis failed for transcription {transcription_id}: {llm_error}")
            
            # Create failed analysis result
            failed_result = AnalysisResult(
                analysisType=analysis_type.name,
                analysisTypeId=analysis_type_id,
                content='',
                createdAt=datetime.now(UTC).isoformat(),
                status='failed',
                errorMessage=str(llm_error)
            )
            
            # Add failed result to transcription
            if not transcription.analysisResults:
                transcription.analysisResults = []
            transcription.analysisResults.append(failed_result)
            
            # Save updated transcription
            transcription_handler.update_transcription(transcription)
            
            return jsonify({
                'status': 'error',
                'message': 'Analysis failed',
                'data': failed_result.model_dump()
            }), 500
        
    except Exception as e:
        logger.error(f"Error executing analysis: {e}")
        return jsonify({'error': 'Failed to execute analysis'}), 500