from audiostream_api.chunk_storage import ChunkStorage
import logging

class InMemoryChunkStorage(ChunkStorage):
    def __init__(self):
        self.sessions = {}

    def start_session(self, session_id: str) -> None:
        self.sessions[session_id] = {"chunks": {}, "completed": False, "number_of_expected_chunks": None}

    def store_chunk(self, session_id: str, chunk_id: int, data: bytes) -> None:
        if session_id not in self.sessions:
            raise ValueError("Session does not exist.")
        self.sessions[session_id]["chunks"][chunk_id] = data

    def retrieve_chunk(self, session_id: str, chunk_id: int) -> bytes:
        return self.sessions.get(session_id, {}).get("chunks", {}).get(chunk_id, b'')

    def get_all_chunks(self, session_id: str) -> list[bytes]:
        if session_id not in self.sessions:
            raise ValueError("Session does not exist.")
        session_chunks = self.sessions[session_id]["chunks"]
        chunks = []
        for chunk_id in sorted(session_chunks.keys()):
            logging.info(f"retrieving chunk {chunk_id}")
            chunks.append(session_chunks[chunk_id])
        return chunks

    def finish_session(self, session_id: str, number_of_expected_chunks: int) -> None:
        """Mark the session as finished and set the total expected chunks."""
        if session_id not in self.sessions:
            raise ValueError("Session does not exist.")
        self.sessions[session_id]["number_of_expected_chunks"] = number_of_expected_chunks
        self.sessions[session_id]["completed"] = True

    def check_missing_chunks(self, session_id: str) -> list[int]:
        if session_id not in self.sessions:
            raise ValueError("Session does not exist.")
        session = self.sessions[session_id]

        chunks = session["chunks"]
        number_of_expected_chunks = session["number_of_expected_chunks"]
        
        # If the session is finished and we know the expected number of chunks
        if session["completed"] and number_of_expected_chunks is not None:
            expected_chunks = set(range(number_of_expected_chunks))
            received_chunks = set(chunks.keys())
            missing_chunks = list(expected_chunks - received_chunks)
            return sorted(missing_chunks)
        else:
            # If the session is not finished or number_of_expected_chunks is unknown, assume all received are correct.
            return []

    def delete_session(self, session_id: str) -> None:
        if session_id in self.sessions:
            del self.sessions[session_id]
