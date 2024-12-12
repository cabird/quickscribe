import os
import requests
import base64
import subprocess
import sys
import logging
import uuid
#set the logging level to info
logging.basicConfig(level=logging.INFO)
API_BASE_URL = "http://127.0.0.1:5000/audiostream"
CHUNK_DURATION = 10  # seconds

def split_audio(file_path, output_dir="chunks"):
    """Splits an audio file into chunks of specified duration using ffmpeg."""
    os.makedirs(output_dir, exist_ok=True)
    chunk_pattern = os.path.join(output_dir, "chunk_%03d.mp3")
    logging.info(f"Splitting audio file into chunks of {CHUNK_DURATION} seconds and storing in {output_dir}")
    subprocess.run(["ffmpeg", "-i", file_path, "-f", "segment", "-segment_time", str(CHUNK_DURATION), "-c", "copy", chunk_pattern])
    logging.info(f"Audio file split into chunks and stored in {output_dir}")
    
    # Return list of chunk paths
    return [os.path.join(output_dir, f) for f in sorted(os.listdir(output_dir)) if f.startswith("chunk_")]

def upload_chunk(session_id, chunk_path, chunk_id):
    """Uploads a single chunk to the server."""
    with open(chunk_path, "rb") as f:
        files = {"chunk_data": f}
        response = requests.post(f"{API_BASE_URL}/upload_chunk", files=files, data={"session_id": session_id, "chunk_id": chunk_id})
        if response.status_code != 200:
            logging.error(f"Failed to upload chunk {chunk_id}: {response.text}")
            return False
        else:
            logging.info(f"Uploaded chunk {chunk_id}.  Response: {response.json()}")
    return True

def finish_recording(session_id, number_of_chunks):
    """Notifies the server that the recording is complete."""
    response = requests.post(f"{API_BASE_URL}/finish", json={"session_id": session_id, "number_of_chunks": number_of_chunks})
    if response.status_code == 200:
        logging.info("Recording finished successfully.")
    else:
        logging.error(f"Failed to finish recording: {response.text}")

def get_full_audio(session_id, output_file):
    """Retrieves the combined audio from the server and saves it as an MP3 file."""
    response = requests.post(f"{API_BASE_URL}/get_full_audio", json={"session_id": session_id})
    if response.status_code == 200:
        # Decode the base64 audio data and write it to file
        audio_data = base64.b64decode(response.json()["full_audio"])
        with open(output_file, "wb") as f:
            f.write(audio_data)
        logging.info(f"Full audio saved as {output_file}")
    else:
        logging.error(f"Failed to retrieve full audio: {response.text}")

def main(mp3_path):
    session_id = "test_session_" + str(uuid.uuid4())
    logging.info(f"Starting recording session with id: {session_id}")
    response = requests.post(f"{API_BASE_URL}/start", json={"session_id": session_id})
    if response.status_code != 200:
        logging.error(f"Failed to start recording session: {response.text}")
        return
    else:
        #output the response
        logging.info(f"Recording session started successfully: {response.json()}")
        
    
    # Step 1: Split the audio file into chunks
    logging.info(f"Splitting audio file into chunks of {CHUNK_DURATION} seconds")
    chunks = split_audio(mp3_path)
    logging.info(f"Audio file split into {len(chunks)} chunks")

    # Step 2: Upload each chunk to the server
    for i, chunk in enumerate(chunks):
        logging.info(f"Uploading chunk {i} to server")
        #TODO - randomly fail some chunks
        if i % 4 == 0:
            logging.info(f"intentionally failing chunk {i}")
            continue
        success = upload_chunk(session_id, chunk, chunk_id=i)
        if not success:
            logging.error(f"Stopping due to failure on chunk {i}")
            return

    logging.info(f"All chunks uploaded")
    # Step 3: Notify the server that the recording is finished
    finish_recording(session_id, len(chunks))
    logging.info(f"Recording finished")

    # Step 4: check for missing chunks
    while True: 
        response = requests.get(f"{API_BASE_URL}/check_missing", params={"session_id": session_id})
        if response.status_code == 200:
            missing_chunks = response.json().get("missing_chunks", [])
            if len(missing_chunks) == 0:
                logging.info(f"No missing chunks found, success!")
                break
            else:
                logging.info(f"Missing chunks: {missing_chunks}")
                #send the missing chunks to the server
                chunks_attempted = 0
                for chunk_id in missing_chunks:
                    if chunks_attempted % 3 == 2:
                        logging.info(f"intentionally failing chunk {chunk_id}")
                        chunks_attempted += 1
                        continue
                    success = upload_chunk(session_id, chunks[chunk_id], chunk_id)
                    if not success:
                        logging.error(f"Stopping due to failure on chunk {chunk_id}")
                        return
                    chunks_attempted += 1
        else:
            logging.error(f"Failed to check for missing chunks: {response.text}")
            break

    
    # Step 4: Retrieve the full audio file
    output_file = "combined_audio.mp3"
    logging.info(f"Retrieving full audio from server")
    get_full_audio(session_id, output_file)
    logging.info(f"Full audio retrieved successfully and saved as {output_file}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_recording_api.py <path_to_mp3_file>")
        sys.exit(1)

    mp3_path = sys.argv[1]
    main(mp3_path)
