from .recording_handler import RecordingHandler
from .transcription_handler import TranscriptionHandler
from .user_handler import UserHandler
from config import config

from flask import g

def get_recording_handler():
    if not hasattr(g, 'recording_handler'):
        g.recording_handler = create_recording_handler()
    return g.recording_handler

def get_transcription_handler():
    if not hasattr(g, 'transcription_handler'):
        g.transcription_handler = create_transcription_handler()
    return g.transcription_handler

def get_user_handler():
    if not hasattr(g, 'user_handler'):
        g.user_handler = create_user_handler()
    return g.user_handler

def create_recording_handler():
    return RecordingHandler(config.COSMOS_URL, config.COSMOS_KEY, config.COSMOS_DB_NAME, config.COSMOS_CONTAINER_NAME)

def create_transcription_handler():
    return TranscriptionHandler(config.COSMOS_URL, config.COSMOS_KEY, config.COSMOS_DB_NAME, config.COSMOS_CONTAINER_NAME)

def create_user_handler():
    return UserHandler(config.COSMOS_URL, config.COSMOS_KEY, config.COSMOS_DB_NAME, config.COSMOS_CONTAINER_NAME)
