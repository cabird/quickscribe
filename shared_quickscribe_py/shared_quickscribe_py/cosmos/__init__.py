"""
Cosmos DB models and handlers
"""
from . import models
from .recording_handler import Recording, RecordingHandler
from .transcription_handler import Transcription, TranscriptionHandler
from .user_handler import User, PlaudSettings, UserHandler
from .analysis_type_handler import AnalysisTypeHandler
from .participant_handler import ParticipantHandler
from .sync_progress_handler import SyncProgressHandler
from .locks_handler import LocksHandler
from .job_execution_handler import JobExecutionHandler
from .manual_review_handler import ManualReviewItemHandler
from .deleted_items_handler import DeletedItems, DeletedItemsHandler

# Handler factory functions (only available in backend with config module)
try:
    from .handler_factory import (
        get_user_handler,
        get_recording_handler,
        get_transcription_handler,
        get_analysis_type_handler,
        get_participant_handler,
        get_sync_progress_handler,
        get_job_execution_handler,
        get_deleted_items_handler,
        create_user_handler,
        create_recording_handler,
        create_transcription_handler,
        create_analysis_type_handler,
        create_participant_handler,
        create_sync_progress_handler,
        create_job_execution_handler,
        create_deleted_items_handler,
    )
    _has_factory = True
except ImportError:
    # Factory functions not available without config module
    _has_factory = False

from .util import filter_cosmos_fields
from .helpers import slugify

# Import commonly used models and enums
from .models import (
    TranscriptionStatus,
    TranscodingStatus,
    Source,
    Tag,
    AnalysisType,
    AnalysisResult,
    Participant,
    PlaudMetadata,
    SyncProgress,
    CreateAnalysisTypeRequest,
    ExecuteAnalysisRequest,
    UpdateAnalysisTypeRequest,
    JobExecution,
    JobExecutionStats,
    JobLogEntry,
    ManualReviewItem,
    FailureRecord,
)

__all__ = [
    "models",
    # Handlers
    "Recording",
    "RecordingHandler",
    "Transcription",
    "TranscriptionHandler",
    "User",
    "PlaudSettings",
    "UserHandler",
    "AnalysisTypeHandler",
    "ParticipantHandler",
    "SyncProgressHandler",
    "LocksHandler",
    "JobExecutionHandler",
    "ManualReviewItemHandler",
    "DeletedItems",
    "DeletedItemsHandler",
    # Models and enums
    "TranscriptionStatus",
    "TranscodingStatus",
    "Source",
    "Tag",
    "AnalysisType",
    "AnalysisResult",
    "Participant",
    "PlaudMetadata",
    "SyncProgress",
    "CreateAnalysisTypeRequest",
    "ExecuteAnalysisRequest",
    "UpdateAnalysisTypeRequest",
    "JobExecution",
    "JobExecutionStats",
    "JobLogEntry",
    "ManualReviewItem",
    "FailureRecord",
    # Utilities
    "filter_cosmos_fields",
    "slugify",
]

# Add factory functions to __all__ if available
if _has_factory:
    __all__.extend([
        "get_user_handler",
        "get_recording_handler",
        "get_transcription_handler",
        "get_analysis_type_handler",
        "get_participant_handler",
        "get_sync_progress_handler",
        "get_job_execution_handler",
        "get_deleted_items_handler",
        "create_user_handler",
        "create_recording_handler",
        "create_transcription_handler",
        "create_analysis_type_handler",
        "create_participant_handler",
        "create_sync_progress_handler",
        "create_job_execution_handler",
        "create_deleted_items_handler",
    ])
