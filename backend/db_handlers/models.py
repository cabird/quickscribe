# generated by datamodel-codegen:
#   filename:  models.schema.json
#   timestamp: 2024-11-01T22:21:57+00:00

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, RootModel


class Model(RootModel[Any]):
    root: Any


class TranscriptionStatus(Enum):
    completed = 'completed'
    failed = 'failed'
    in_progress = 'in_progress'
    not_started = 'not_started'


class Recording(BaseModel):
    az_transcription_id: Optional[str] = None
    duration: Optional[float] = None
    id: str
    original_filename: str
    partitionKey: str
    transcription_error_message: Optional[str] = None
    transcription_id: Optional[str] = None
    transcription_status: TranscriptionStatus
    transcription_status_updated_at: Optional[str] = None
    unique_filename: str
    upload_timestamp: Optional[str] = None
    user_id: str


class SpeakerMapping(BaseModel):
    name: str
    reasoning: str


class Transcription(BaseModel):
    az_raw_transcription: Optional[str] = None
    az_transcription_id: Optional[str] = None
    diarized_transcript: Optional[str] = None
    id: str
    partitionKey: str
    recording_id: str
    speaker_mapping: Optional[Dict[str, SpeakerMapping]] = None
    text: Optional[str] = None
    transcript_json: Optional[str] = None
    user_id: str


class User(BaseModel):
    created_at: Optional[str] = None
    email: Optional[str] = None
    id: str
    last_login: Optional[str] = None
    name: Optional[str] = None
    partitionKey: str
    role: Optional[str] = None
