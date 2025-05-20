# transcoder_container/main.py - Updated for audio transcoding with Storage Queues

import os
import sys
import json
import asyncio
import logging
import tempfile
import subprocess
from datetime import datetime
from azure.storage.queue import QueueClient
from container_app_version import CONTAINER_APP_VERSION
import time
import requests
import traceback

from dotenv import load_dotenv
# Load environment variables from .env file
load_dotenv()

#define the application namespace for logging
app_namespace = "quickscribe.transcoder"  # Replace with your application's name

#write all environment variables to the console
for key in ["APPLICATIONINSIGHTS_CONNECTION_STRING", 
                   "APPLICATIONINSIGHTS_USE_OPENCENSUS", 
                   ]:
    print(f"{key}: {os.environ.get(key)}")

# Configure logging for Azure
# Import Azure Monitor OpenTelemetry integration
from opencensus.ext.azure.log_exporter import AzureLogHandler

# Configure logging for Azure
def setup_azure_logging():
    """Configure logging optimized for Azure Container Apps/Instances with Application Insights integration"""
    
    
    # Configure Azure Monitor with your application's namespace
    # This will use the APPLICATIONINSIGHTS_CONNECTION_STRING environment variable
    #if 'APPLICATIONINSIGHTS_CONNECTION_STRING' in os.environ:
    #    configure_azure_monitor(
    #        logger_name=app_namespace,  # Only collect logs from your application namespace
    #    )
    
    # Create custom formatter with JSON output for structured logs
    class JSONFormatter(logging.Formatter):
        def format(self, record):
            log_obj = {
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'level': record.levelname,
                'logger': record.name,
                'message': record.getMessage(),
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno
            }
            
            # Add extra fields if present
            if hasattr(record, 'recording_id'):
                log_obj['recording_id'] = record.recording_id
            if hasattr(record, 'action'):
                log_obj['action'] = record.action
            if hasattr(record, 'user_id'):
                log_obj['user_id'] = record.user_id
            
            # If record has custom_dimensions (for App Insights), include them
            if hasattr(record, 'custom_dimensions'):
                for key, value in record.custom_dimensions.items():
                    log_obj[key] = value
                
            return json.dumps(log_obj)
        
        # Custom filter to move additional attributes into custom_dimensions
    class MetadataFilter(logging.Filter):
        def filter(self, record):
            # Initialize custom_dimensions if not present
            if not hasattr(record, 'custom_dimensions'):
                record.custom_dimensions = {}

            record.custom_dimensions['service'] = "quickscribe"
            record.custom_dimensions['app_namespace'] = app_namespace
            record.custom_dimensions['container_version'] = CONTAINER_APP_VERSION
            
            # Add specific attributes to custom_dimensions if they exist
            for attr in ['recording_id', 'action', 'user_id']:
                if hasattr(record, attr):
                    record.custom_dimensions[attr] = getattr(record, attr)
                    # Optionally: remove from record to prevent it from appearing in other formatters
                    # delattr(record, attr)
            
            return True  # Always include the record
    
    # Configure app logger (not root logger, to avoid SDK logs)
    logger = logging.getLogger(app_namespace)
    logger.setLevel(logging.INFO)
    logger.propagate = False  # Don't propagate to root logger

    # Add the filter that will process metadata
    logger.addFilter(MetadataFilter())
    
    # Remove default handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create console handler with JSON formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(JSONFormatter())
    logger.addHandler(console_handler)
    
    # Set Azure-specific log level from environment
    log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
    logger.setLevel(getattr(logging, log_level, logging.INFO))
    
    # If App Insights connection string is available but we're using the older SDK approach
    # as a fallback, add the AzureLogHandler explicitly
    if 'APPLICATIONINSIGHTS_CONNECTION_STRING' in os.environ:        
        # Add Azure Application Insights handler
        azure_handler = AzureLogHandler(
            connection_string=os.environ.get('APPLICATIONINSIGHTS_CONNECTION_STRING')
        )

        azure_handler.setFormatter(logging.Formatter('%(message)s'))  # Use default formatter for Azure logs
        logger.addHandler(azure_handler)
    
    return logger

logger = setup_azure_logging()

# Configure logging
#logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
#logger = logging.getLogger(__name__)

# Enhanced logging with context
class ContextLogger:
    def __init__(self, base_logger, **context):
        self.base_logger = base_logger
        self.context = context
    
    def info(self, message, **extra):
        self._log(logging.INFO, message, **extra)
    
    def error(self, message, **extra):
        self._log(logging.ERROR, message, **extra)
    
    def warning(self, message, **extra):
        self._log(logging.WARNING, message, **extra)
    
    def debug(self, message, **extra):
        self._log(logging.DEBUG, message, **extra)
    
    def _log(self, level, message, **extra):
        # Merge context with extra fields
        combined = {**self.context, **extra}
        self.base_logger.log(level, message, extra=combined)

# Environment variables
AZURE_STORAGE_CONNECTION_STRING = os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
TRANSCODING_QUEUE_NAME = os.environ.get('TRANSCODING_QUEUE_NAME')

# Processing timeout (30 minutes)
PROCESSING_TIMEOUT = 30 * 60  # seconds
MAX_RETRIES = 3

class TranscodingProcessor:
    def __init__(self):
        self.queue_client = QueueClient.from_connection_string(
            AZURE_STORAGE_CONNECTION_STRING, 
            TRANSCODING_QUEUE_NAME
        )

    def get_file_metadata(self, file_path: str) -> dict:
        """Extract metadata from audio file using ffprobe"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json', 
                '-show_format', '-show_streams', file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.warning(f"Could not extract metadata from {file_path}")
                return {}
            
            data = json.loads(result.stdout)
            
            # Extract relevant metadata
            metadata = {}
            if 'format' in data:
                format_info = data['format']
                metadata['duration'] = float(format_info.get('duration', 0))
                metadata['size_bytes'] = int(format_info.get('size', 0))
                metadata['format'] = format_info.get('format_name', 'unknown')
                
                # Extract bitrate if available
                if 'bit_rate' in format_info:
                    bitrate_bps = int(format_info['bit_rate'])
                    metadata['bitrate'] = f"{bitrate_bps // 1000}k"
            
            # Extract codec info from streams
            if 'streams' in data:
                for stream in data['streams']:
                    if stream.get('codec_type') == 'audio':
                        metadata['codec'] = stream.get('codec_name', 'unknown')
                        break
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")
            return {}
    
    def convert_to_mp3(self, source_file_path: str, target_file_path: str) -> None:
        """Convert audio file to MP3 format using ffmpeg"""
        # Valid file extensions (from original code)
        valid_extensions = ["mp3", "m4a"]
        
        extension = os.path.splitext(source_file_path)[1][1:].lower()
        if extension not in valid_extensions:
            raise ValueError(f"Unsupported file type. Only {', '.join(valid_extensions)} files are supported.")
        

        # Use ffmpeg to convert to MP3 with single channel and 128k bitrate
        cmd = [
            'ffmpeg', '-i', source_file_path,
            '-c:a', 'libmp3lame', '-q:a', '2', '-ac', '1', '-ar', '44100',
            target_file_path, '-y'  # -y overwrites output files
        ]
        
        logger.info(f"Running ffmpeg command: {' '.join(cmd)}")
        #start a timer
        start_time = time.time()
        # Run ffmpeg command
        process = subprocess.run(cmd, capture_output=True, text=True)
        #get elapsed time
        elapsed_time = time.time() - start_time
        logger.info(f"ffmpeg command completed in {elapsed_time:.2f} seconds")
        
        if process.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {process.stderr}")
        
        logger.info("Transcoding completed successfully")

    """Send callbacks to multiple URLs in parallel"""
    def send_single_callback(self, url: str, token: str, response_data: dict):
        # Add the callback token to the response
        callback_data = response_data.copy()
        callback_data['callback_token'] = token
        
        try:
            response = requests.post(url, json=callback_data, timeout=30)
            if response.status_code == 200:
                logger.info(f"Successfully sent callback to {url}")
            else:
                logger.error(f"Callback to {url} failed with status {response.status_code}: {response.text}")
        except requests.exceptions.Timeout:
            logger.error(f"Callback to {url} timed out after 30 seconds")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send callback to {url}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error sending callback to {url}: {e}")
    
    def send_callbacks(self, callbacks: list, response_data: dict):
        """Send callbacks to multiple URLs"""
        # Send all callbacks in parallel
        for callback in callbacks:
            self.send_single_callback(callback['url'], callback['token'], response_data)
    
    def handle_test_action(self, message_content: dict) -> None:
        """Handle test action - simple health check"""
        logger.info("Processing test action")
        
        callbacks = message_content.get('callbacks', [])
        content = message_content.get('content', '')
        
        # Prepare response
        response_data = {
            'action': 'test',
            'status': 'completed',
            'container_version': CONTAINER_APP_VERSION,
            'content': content,
            'message': f'Container is healthy and operational. Received content: "{content}"',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Send callbacks
        self.send_callbacks(callbacks, response_data)
        logger.info("Test action completed successfully")
    
    def handle_transcode_action(self, message_content: dict) -> None:
        """Handle transcode action"""
        recording_id = message_content.get('recording_id')
        source_sas_url = message_content.get('source_sas_url')
        target_sas_url = message_content.get('target_sas_url')
        original_filename = message_content.get('original_filename')
        callbacks = message_content.get('callbacks', [])
        user_id = message_content.get('user_id')

        # Create context logger for this recording
        ctx_logger = ContextLogger(
            logger, 
            original_filename=original_filename,
            recording_id=recording_id,
            action='transcode',
            user_id=user_id
        )
        
        ctx_logger.info(f"Processing transcode action for recording {recording_id}")
        
        # Validate required fields
        if not all([recording_id, source_sas_url, target_sas_url, callbacks]):
            ctx_logger.error(f"Missing required fields in transcode message: {message_content}")
            return
        
        # Send initial in_progress callback
        in_progress_response = {
            'action': 'transcode',
            'recording_id': recording_id,
            'original_filename': original_filename,
            'status': 'in_progress',
            'container_version': CONTAINER_APP_VERSION
        }
        self.send_callbacks(callbacks, in_progress_response)
        
        # Create temporary files
        source_temp_file = None
        target_temp_file = None
        
        try:
            # Start timeout timer
            start_time = time.time()
            
            # Download source file
            ctx_logger.info(f"Downloading source file from SAS URL: {source_sas_url}")
            #get the extension from the original filename
            source_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(original_filename)[1])
            
            response = requests.get(source_sas_url)
            if response.status_code != 200:
                raise RuntimeError(f"Failed to download source file.  Status code: {response.status_code}")
                
            content = response.content
            source_temp_file.write(content)
            source_temp_file.close()
            
            # Get input metadata
            input_metadata = self.get_file_metadata(source_temp_file.name)
            ctx_logger.info(f"Input metadata: {input_metadata}")
            
            # Check timeout
            if time.time() - start_time > PROCESSING_TIMEOUT:
                raise TimeoutError("Processing timeout exceeded during download")
            
            # Create temporary file for output
            target_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
            target_temp_file.close()
            
            # Transcode the file
            ctx_logger.info(f"Transcoding {source_temp_file.name} to {target_temp_file.name}")
            self.convert_to_mp3(source_temp_file.name, target_temp_file.name)
            
            # Get output metadata
            output_metadata = self.get_file_metadata(target_temp_file.name)
            ctx_logger.info(f"Output metadata: {output_metadata}")
            
            # Check timeout
            if time.time() - start_time > PROCESSING_TIMEOUT:
                raise TimeoutError("Processing timeout exceeded during transcoding")
            
            # Upload transcoded file
            ctx_logger.info(f"Uploading transcoded file to SAS URL")
            with open(target_temp_file.name, 'rb') as upload_file:
                try:
                    # Adding the required x-ms-blob-type header for Azure Blob Storage
                    headers = {
                        'x-ms-blob-type': 'BlockBlob',
                        'Content-Type': 'audio/mpeg'
                    }
                    ctx_logger.info(f"Uploading with headers: {headers}")
                    response = requests.put(
                        target_sas_url, 
                        data=upload_file, 
                        headers=headers,
                        timeout=300
                    )  # 5 minute timeout
                    response.raise_for_status()  # Raises exception for bad status codes
                    logger.info(f"Successfully uploaded transcoded file")
                except requests.exceptions.RequestException as e:
                    raise RuntimeError(f"Failed to upload transcoded file: {e}")
                except Exception as e:
                    raise RuntimeError(f"Unexpected error uploading file: {e}")
            
            # Check timeout
            if time.time() - start_time > PROCESSING_TIMEOUT:
                raise TimeoutError("Processing timeout exceeded during upload")
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Send success callback
            success_response = {
                'action': 'transcode',
                'recording_id': recording_id,
                'status': 'completed',
                'container_version': CONTAINER_APP_VERSION,
                'processing_time': round(processing_time, 2),
                'input_metadata': input_metadata,
                'output_metadata': output_metadata
            }
            
            self.send_callbacks(callbacks, success_response)
            ctx_logger.info(f"Successfully completed transcoding for recording {recording_id} in {processing_time:.2f} seconds")
            
        except TimeoutError as e:
            ctx_logger.error(f"Transcoding timeout for recording {recording_id}: {e}")
            error_response = {
                'action': 'transcode',
                'recording_id': recording_id,
                'status': 'failed',
                'container_version': CONTAINER_APP_VERSION,
                'error_message': str(e)
            }
            self.send_callbacks(callbacks, error_response)
            
        except Exception as e:
            ctx_logger.error(f"Transcoding failed for recording {recording_id}: {e}")
            #get the traceback as a string
            traceback_str = traceback.format_exc()
            ctx_logger.error(f"Traceback: {traceback_str}")
            error_response = {
                'action': 'transcode',
                'recording_id': recording_id,
                'status': 'failed',
                'container_version': CONTAINER_APP_VERSION,
                'error_message': str(e),
                'traceback': traceback_str
            }
            self.send_callbacks(callbacks, error_response)
            
        finally:
            # Clean up temporary files
            if source_temp_file and os.path.exists(source_temp_file.name):
                os.unlink(source_temp_file.name)
            if target_temp_file and os.path.exists(target_temp_file.name):
                os.unlink(target_temp_file.name)
    

    def process_message(self, message_content: dict) -> None:
        """Process a message based on its action type"""
        action = message_content.get('action')
        
        if action == 'test':
            self.handle_test_action(message_content)
        elif action == 'transcode':
            self.handle_transcode_action(message_content)
        else:
            logger.error(f"Unknown action: {action}")
            # If there are callbacks, notify them of the error
            callbacks = message_content.get('callbacks', [])
            if callbacks:
                error_response = {
                    'action': action,
                    'status': 'failed',
                    'container_version': CONTAINER_APP_VERSION,
                    'error_message': f'Unknown action: {action}'
                }
                self.send_callbacks(callbacks, error_response)

    def run(self):
        """Main processing loop"""
        logger.info(f"Starting transcoding processor v{CONTAINER_APP_VERSION}...")
        
        try:
            message_count = 0
            for message in self.queue_client.receive_messages():
                message_count += 1
                try:
                    # Parse message content
                    message_content = json.loads(message.content)
                    logger.info(f"Received message: {message_content}")
                    
                    # Process the transcoding job
                    self.process_message(message_content)
                    
                    # Delete message from queue on success
                    self.queue_client.delete_message(message)
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in message: {e}")
                    self.queue_client.delete_message(message)  # Remove invalid message
                    
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    # Don't delete message - it will be retried (up to max retries)
            logger.info(f"Processing loop completed, processed {message_count} messages")        
        except Exception as e:
            logger.error(f"Error in main processing loop: {e}")
            raise
        
        finally:
            logger.info("Closing queue client")
            self.queue_client.close()


def main():
    """Main entry point"""
    # Validate environment variables
    required_vars = [
        'AZURE_STORAGE_CONNECTION_STRING',
        'TRANSCODING_QUEUE_NAME',
    ]
    
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        return
    
    processor = TranscodingProcessor()
    
    try:
        processor.run()
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        logger.exception("Traceback:")
        raise

if __name__ == "__main__":
    main()