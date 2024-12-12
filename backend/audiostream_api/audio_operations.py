
import subprocess
import tempfile
import os
from typing import List
import logging

def combine_mp3_chunks_into_one_channel_file(chunks: List[bytes], output_file: str) -> None:
    """
    Combines a list of MP3 chunks into a single MP3 that has just one audio channel using ffmpeg.
    
    Parameters:
        chunks (List[bytes]): A list of MP3 audio chunks as byte objects.
        output_file (str): Path to the final output MP3 file.
    """
    # Create temporary files for each chunk
    temp_files = []
    try:
        for idx, chunk in enumerate(chunks):
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
            temp_file.write(chunk)
            temp_file.close()
            temp_files.append(temp_file.name)

        # Create a text file listing all chunk paths, required for the ffmpeg concat filter
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as list_file:
            for temp_file in temp_files:
                list_file.write(f"file '{temp_file}'\n".encode())
            list_file_path = list_file.name

        # Use ffmpeg to concatenate all chunks into one output file
        ffmpeg_command = [
            'ffmpeg', '-f', 'concat', '-safe', '0', '-i', list_file_path,
            '-c:a', 'libmp3lame', '-q:a', '1', '-ac', '1', output_file
        ]

        # Run the ffmpeg command
        subprocess.run(ffmpeg_command, check=True)
        print(f"Successfully created {output_file}")
        
    except subprocess.CalledProcessError as e:
        print(f"An error occurred during audio processing: {e}")
    finally:
        # Clean up all temporary files
        for temp_file in temp_files:
            os.unlink(temp_file)
        if os.path.exists(list_file_path):
            os.unlink(list_file_path)
