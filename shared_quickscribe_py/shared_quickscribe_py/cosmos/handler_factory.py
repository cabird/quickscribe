from .recording_handler import RecordingHandler
from .transcription_handler import TranscriptionHandler
from .user_handler import UserHandler
from .sync_progress_handler import SyncProgressHandler
from .analysis_type_handler import AnalysisTypeHandler
from .participant_handler import ParticipantHandler
from .job_execution_handler import JobExecutionHandler
from .deleted_items_handler import DeletedItemsHandler
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

def get_sync_progress_handler():
    if not hasattr(g, 'sync_progress_handler'):
        g.sync_progress_handler = create_sync_progress_handler()
    return g.sync_progress_handler

def get_analysis_type_handler():
    if not hasattr(g, 'analysis_type_handler'):
        g.analysis_type_handler = create_analysis_type_handler()
    return g.analysis_type_handler

def get_participant_handler():
    if not hasattr(g, 'participant_handler'):
        g.participant_handler = create_participant_handler()
    return g.participant_handler

def get_job_execution_handler():
    if not hasattr(g, 'job_execution_handler'):
        g.job_execution_handler = create_job_execution_handler()
    return g.job_execution_handler

def get_deleted_items_handler():
    if not hasattr(g, 'deleted_items_handler'):
        g.deleted_items_handler = create_deleted_items_handler()
    return g.deleted_items_handler

def create_recording_handler():
    return RecordingHandler(config.COSMOS_URL, config.COSMOS_KEY, config.COSMOS_DB_NAME, config.COSMOS_CONTAINER_NAME)

def create_transcription_handler():
    return TranscriptionHandler(config.COSMOS_URL, config.COSMOS_KEY, config.COSMOS_DB_NAME, config.COSMOS_CONTAINER_NAME)

def create_user_handler():
    return UserHandler(config.COSMOS_URL, config.COSMOS_KEY, config.COSMOS_DB_NAME, config.COSMOS_CONTAINER_NAME)

def create_sync_progress_handler():
    from azure.cosmos import CosmosClient
    cosmos_client = CosmosClient(config.COSMOS_URL, config.COSMOS_KEY)
    return SyncProgressHandler(cosmos_client, config.COSMOS_DB_NAME)

def create_analysis_type_handler():
    return AnalysisTypeHandler(config.COSMOS_URL, config.COSMOS_KEY, config.COSMOS_DB_NAME, 'analysis_types')

def create_participant_handler():
    return ParticipantHandler(config.COSMOS_URL, config.COSMOS_KEY, config.COSMOS_DB_NAME, config.COSMOS_CONTAINER_NAME)

def create_job_execution_handler():
    return JobExecutionHandler(config.COSMOS_URL, config.COSMOS_KEY, config.COSMOS_DB_NAME, config.COSMOS_CONTAINER_NAME)

def create_deleted_items_handler():
    return DeletedItemsHandler(config.COSMOS_URL, config.COSMOS_KEY, config.COSMOS_DB_NAME, config.COSMOS_CONTAINER_NAME)
