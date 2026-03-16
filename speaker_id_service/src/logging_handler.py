"""
Custom logging handler that logs to both stdout and an in-memory array for Cosmos DB storage.
Copied from plaud_sync_service with minimal adaptation.
"""
import logging
import sys
import collections
from datetime import datetime, UTC
from typing import List, Dict, Any, Deque
from threading import Lock

from shared_quickscribe_py.cosmos.models import JobLogEntry


class JobLogger:
    """
    Custom logger that captures log messages for both console output and Cosmos DB storage.
    Thread-safe for concurrent logging.
    """

    def __init__(self, job_id: str, log_level: str = "INFO"):
        self.job_id = job_id
        self.logs: Deque[Dict[str, Any]] = collections.deque(maxlen=1000)
        self.lock = Lock()

        self.logger = logging.getLogger(f"speaker_id_{job_id}")
        self.logger.setLevel(getattr(logging, log_level))

        self.logger.handlers = []

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level))

        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

    def _log(self, level: str, message: str, recording_id: str = None):
        """Internal method to log to both console and in-memory array."""
        log_method = getattr(self.logger, level.lower())
        log_method(message)

        with self.lock:
            log_entry = {
                "timestamp": datetime.now(UTC).isoformat(),
                "level": level.lower(),
                "message": message
            }
            if recording_id:
                log_entry["recordingId"] = recording_id
            self.logs.append(log_entry)

    def debug(self, message: str, recording_id: str = None):
        self._log("debug", message, recording_id)

    def info(self, message: str, recording_id: str = None):
        self._log("info", message, recording_id)

    def warning(self, message: str, recording_id: str = None):
        self._log("warning", message, recording_id)

    def error(self, message: str, recording_id: str = None):
        self._log("error", message, recording_id)

    def get_logs(self) -> List[JobLogEntry]:
        """Get all captured logs for Cosmos DB storage as JobLogEntry objects."""
        with self.lock:
            return [
                JobLogEntry(
                    timestamp=log["timestamp"],
                    level=log["level"],
                    message=log["message"],
                    recordingId=log.get("recordingId")
                )
                for log in self.logs
            ]

    def clear_logs(self):
        """Clear the in-memory log array."""
        with self.lock:
            self.logs.clear()
