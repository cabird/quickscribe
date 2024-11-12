from flask import Blueprint, request, jsonify
from audiostream_api.in_memory_chunk_storage import InMemoryChunkStorage  # Import your storage class
from audiostream_api.audio_operations import combine_mp3_chunks
import os
import logging
import base64


audiostream_api_bp = Blueprint('audiostream_api', __name__)
chunk_storage = InMemoryChunkStorage()  # Initialize the in-memory storage for audio chunks

@audiostream_api_bp.route('/start', methods=['POST'])
def start_stream():
    data = request.json
    session_id = data.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400
    logging.info(f"Starting audio stream session with id: {session_id}")

    chunk_storage.start_session(session_id)
    return jsonify({"message": "Audio stream session started", "session_id": session_id}), 200


@audiostream_api_bp.route('/upload_chunk', methods=['POST'])
def receive_chunk():
    session_id = request.form.get("session_id")
    chunk_id = request.form.get("chunk_id")
    #try to convert to int
    try:
        chunk_id = int(chunk_id)
    except ValueError:
        return jsonify({"error": "chunk_id must be an integer"}), 400

    logging.info(f"Receiving chunk {chunk_id} for session {session_id}")
    # list the files in the request
    logging.info(f"Files in request: {request.files}")
    chunk_data = request.files.get("chunk_data")
    
    if not session_id or chunk_id is None or not chunk_data:
        return jsonify({"error": "session_id, chunk_id, and chunk_data are required"}), 400

    # Store the chunk in the storage system
    chunk_storage.store_chunk(session_id, chunk_id, chunk_data.read())
    return jsonify({"message": "Chunk received", "chunk_id": chunk_id}), 200


@audiostream_api_bp.route('/finish', methods=['POST'])
def finish_stream():
    data = request.json
    session_id = data.get("session_id")
    number_of_chunks = data.get("number_of_chunks")
    #try to convert to int
    try:
        number_of_chunks = int(number_of_chunks)
    except ValueError:
        return jsonify({"error": "number_of_chunks must be an integer"}), 400

    if not session_id or number_of_chunks is None:
        return jsonify({"error": "session_id and number_of_chunks are required"}), 400

    # Mark the session as finished and set the expected total chunks
    chunk_storage.finish_session(session_id, number_of_chunks)
    missing_chunks = chunk_storage.check_missing_chunks(session_id)
    
    if missing_chunks:
        return jsonify({"status": "incomplete", "missing_chunks": missing_chunks}), 206

    # Combine chunks and create the audio recording item in Cosmos DB (placeholder function)
    create_audio_recording_in_db(session_id)
    return jsonify({"status": "complete", "message": "Audio stream complete"}), 200


@audiostream_api_bp.route('/check-missing', methods=['GET'])
def check_missing_chunks():
    session_id = request.args.get("session_id")
    
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400
    
    missing_chunks = chunk_storage.check_missing_chunks(session_id)
    return jsonify({"missing_chunks": missing_chunks}), 200

@audiostream_api_bp.route('/get_full_audio', methods=['POST'])
def get_full_audio():
    session_id = request.json.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400

    combined_audio = create_audio_recording_in_db(session_id)
    encoded_audio = base64.b64encode(combined_audio).decode('utf-8')
    
    return jsonify({"full_audio": encoded_audio}), 200


def create_audio_recording_in_db(session_id: str):
    """Placeholder function to simulate audio recording creation in the database."""
    # Retrieve and process all chunks for the session
    all_chunks = chunk_storage.get_all_chunks(session_id)
    # create a temp file to store the combined audio, but use the session_id as the filename    
    temp_file_path = f"/tmp/{session_id}.mp3"
    logging.info(f"Creating temp combined audio file at {temp_file_path}")
    combined_audio = combine_mp3_chunks(all_chunks, temp_file_path)
    logging.info(f"Combined audio file completed at {temp_file_path}")

    #now read the file into a bytes object
    with open(temp_file_path, 'rb') as file:
        combined_audio = file.read()
    
    #delete the temp file
    if os.path.exists(temp_file_path):
        os.remove(temp_file_path)
    
    # Here, you would store the combined audio as a single file or in a database
    # Additionally, create a new Recording item in Cosmos DB (pseudo-code):
    # cosmos_db.create_recording(session_id, audio_data=combined_audio)

    print(f"Recording for session {session_id} created in DB with combined audio length: {len(combined_audio)} bytes")
    return combined_audio
