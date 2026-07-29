"""
Speaker Identification Validation UI - Flask Server

This server:
1. Loads speaker identification results from the diarization system
2. Generates validation queues grouped by suggested participant
3. Creates temporary audio URLs from Azure Blob Storage
4. Serves the React-based validation interface
5. Saves validation decisions to JSON files for later batch processing
"""

import mimetypes
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from speaker_identifier import MeetingIdentificationResult
from speaker_embedder import SpeakerProfileDB
from data_loader import DataLoader
from fast_identifier import load_embeddings, fast_identify_from_embeddings, compute_centroid
import numpy as np
from speaker_embedder import cosine_similarity

# CRITICAL: Configure MIME type for .jsx BEFORE creating Flask app
mimetypes.add_type('application/javascript', '.jsx')

app = Flask(__name__, static_folder='.')
CORS(app)

# Configuration
USER_ID = os.environ.get('QUICKSCRIBE_USER_ID', 'user-bd639cf9-a105-44f5-80e0-478a8ec2e5c2')
PROFILES_PATH = os.environ.get('SPEAKER_PROFILES_PATH', '../speaker_profiles.json')
EMBEDDINGS_DIR = os.environ.get('EMBEDDINGS_DIR', '../embeddings')
AUDIO_CACHE_DIR = '../audio_cache'
VALIDATIONS_DIR = './validations'

# Ensure directories exist
os.makedirs(AUDIO_CACHE_DIR, exist_ok=True)
os.makedirs(VALIDATIONS_DIR, exist_ok=True)

# Global state
validation_queue = None
profile_db = None
embeddings_metadata = None
embeddings_data = None
data_loader = None


def load_identification_results(max_meetings: Optional[int] = None) -> List[MeetingIdentificationResult]:
    """Load speaker identification results using pre-computed embeddings."""
    global profile_db, embeddings_metadata, embeddings_data, data_loader

    print(f"\n=== Loading Identification Results (Fast Mode) ===")
    print(f"User ID: {USER_ID}")
    print(f"Profiles: {PROFILES_PATH}")
    print(f"Embeddings: {EMBEDDINGS_DIR}")

    # Load profiles (once)
    if profile_db is None:
        print("\nLoading speaker profiles...")
        profile_db = SpeakerProfileDB.load_from_file(PROFILES_PATH)
        print(f"  Loaded {len(profile_db.profiles)} profiles")

    # Load embeddings (once)
    if embeddings_metadata is None or embeddings_data is None:
        print("\nLoading pre-computed embeddings...")
        embeddings_metadata, embeddings_data = load_embeddings(EMBEDDINGS_DIR)

    # Initialize data loader (once)
    if data_loader is None:
        data_loader = DataLoader()

    # Run fast identification
    print("\nRunning speaker identification...")
    results = fast_identify_from_embeddings(
        profile_db=profile_db,
        metadata=embeddings_metadata,
        embeddings=embeddings_data,
        high_threshold=0.80,
        low_threshold=0.60,
        max_meetings=max_meetings
    )

    # Debug: Count statuses
    total_matches = 0
    auto_count = 0
    suggest_count = 0
    unknown_count = 0

    for result in results:
        for match in result.speaker_matches:
            total_matches += 1
            if match.status == "auto":
                auto_count += 1
            elif match.status == "suggest":
                suggest_count += 1
            else:
                unknown_count += 1

    print(f"\n=== Identification Results Summary ===")
    print(f"Total recordings processed: {len(results)}")
    print(f"Total speaker matches: {total_matches}")
    print(f"  - Auto (>= 0.80): {auto_count}")
    print(f"  - Suggest (0.60-0.80): {suggest_count}")
    print(f"  - Unknown (< 0.60): {unknown_count}")
    print(f"\nValidation UI will show {suggest_count} 'suggest' items")

    return results


def cluster_unknown_speakers(
    results: List[MeetingIdentificationResult],
    embeddings: Dict[str, np.ndarray],
    similarity_threshold: float = 0.70
) -> List[Dict]:
    """
    Cluster unknown speakers (those not matching any known profile).

    Uses Union-Find to build connected components where edges exist
    between speakers with similarity >= threshold.

    Returns list of clusters, each containing:
        - cluster_id: unique identifier
        - items: list of speaker items in the cluster
        - centroid: aggregated embedding for the cluster
    """
    print(f"\n=== Clustering Unknown Speakers ===")

    # Collect all unknown speakers with their embeddings
    unknown_speakers = []
    for result in results:
        for match in result.speaker_matches:
            if match.status == "unknown":
                key = f"{result.recording_id}::{match.speaker_label}"
                if key in embeddings:
                    centroid = compute_centroid(embeddings[key])
                    unknown_speakers.append({
                        'key': key,
                        'recording_id': result.recording_id,
                        'title': result.title,
                        'speaker_label': match.speaker_label,
                        'centroid': centroid,
                        'segment_count': match.segment_count,
                        'total_duration_s': match.total_duration_s
                    })

    print(f"  Found {len(unknown_speakers)} unknown speakers with embeddings")

    if len(unknown_speakers) == 0:
        return []

    # Union-Find data structure
    parent = list(range(len(unknown_speakers)))
    rank = [0] * len(unknown_speakers)

    def find(x):
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x, y):
        px, py = find(x), find(y)
        if px == py:
            return
        if rank[px] < rank[py]:
            px, py = py, px
        parent[py] = px
        if rank[px] == rank[py]:
            rank[px] += 1

    # Build edges based on similarity - use matrix operations for efficiency
    print(f"  Computing pairwise similarities...")

    # Stack all centroids into a matrix for vectorized computation
    centroids_matrix = np.array([s['centroid'] for s in unknown_speakers])
    # Compute all pairwise similarities at once: (n x d) @ (d x n) = (n x n)
    similarity_matrix = centroids_matrix @ centroids_matrix.T

    # Find pairs above threshold (upper triangle only to avoid duplicates)
    edge_count = 0
    for i in range(len(unknown_speakers)):
        for j in range(i + 1, len(unknown_speakers)):
            if similarity_matrix[i, j] >= similarity_threshold:
                union(i, j)
                edge_count += 1

    print(f"  Found {edge_count} edges (similarity >= {similarity_threshold})")

    # Group by connected component
    components = {}
    for i, speaker in enumerate(unknown_speakers):
        root = find(i)
        if root not in components:
            components[root] = []
        components[root].append(speaker)

    # Build cluster objects, sorted by size (largest first)
    clusters = []
    for idx, (root, members) in enumerate(sorted(components.items(), key=lambda x: -len(x[1]))):
        # Compute cluster centroid (average of member centroids)
        centroids = np.array([m['centroid'] for m in members])
        cluster_centroid = centroids.mean(axis=0)
        cluster_centroid = cluster_centroid / (np.linalg.norm(cluster_centroid) + 1e-8)

        # Pick representative (member with highest similarity to cluster centroid)
        best_rep_idx = 0
        best_rep_sim = -1
        for i, m in enumerate(members):
            sim = cosine_similarity(m['centroid'], cluster_centroid)
            if sim > best_rep_sim:
                best_rep_sim = sim
                best_rep_idx = i

        # Remove numpy centroids from items before adding to cluster
        # (numpy arrays are not JSON serializable)
        clean_members = []
        for m in members:
            clean_member = {k: v for k, v in m.items() if k != 'centroid'}
            clean_members.append(clean_member)

        clean_rep = {k: v for k, v in members[best_rep_idx].items() if k != 'centroid'}

        clusters.append({
            'cluster_id': f'cluster-{idx}',
            'size': len(members),
            'representative': clean_rep,
            'items': clean_members
            # Note: centroid intentionally omitted (numpy array not JSON serializable)
        })

    print(f"  Created {len(clusters)} clusters")
    for i, c in enumerate(clusters[:5]):  # Show top 5
        print(f"    Cluster {i}: {c['size']} speakers")
    if len(clusters) > 5:
        print(f"    ... and {len(clusters) - 5} more clusters")

    return clusters


def get_audio_url(recording, speaker_segments, max_duration: float = 8.0) -> Optional[str]:
    """
    Get a temporary SAS URL for audio snippet.

    For now, returns the local audio path. In production, this would generate
    a short-lived Azure Blob Storage SAS URL.
    """
    if not data_loader:
        return None

    try:
        # Download audio to cache
        audio_path = data_loader.download_audio(
            recording,
            output_dir=AUDIO_CACHE_DIR
        )

        # Find the longest segment
        longest_segment = max(speaker_segments, key=lambda s: s.end_s - s.start_s)

        # Get relative path from cache dir (preserves subdirectories like user-xxx/)
        cache_dir = os.path.abspath(AUDIO_CACHE_DIR)
        abs_audio_path = os.path.abspath(audio_path)
        relative_path = os.path.relpath(abs_audio_path, cache_dir)

        return {
            'url': f'/audio/{relative_path}',
            'start': longest_segment.start_s,
            'end': min(longest_segment.end_s, longest_segment.start_s + max_duration)
        }
    except Exception as e:
        print(f"Error getting audio URL: {e}")
        return None


def load_already_validated_items() -> set:
    """Load item_ids that have already been validated from JSON files."""
    validated = set()
    try:
        for filepath in Path(VALIDATIONS_DIR).glob('validation-*.json'):
            with open(filepath, 'r') as f:
                data = json.load(f)
                for decision in data.get('decisions', []):
                    validated.add(decision.get('item_id'))
    except Exception as e:
        print(f"Warning: Error loading validated items: {e}")
    return validated


def build_validation_queue(results: List[MeetingIdentificationResult], clusters: List[Dict] = None) -> Dict:
    """
    Build validation queue grouped by suggested participant.

    Returns dict with:
        - participants: List of participants with their validation items
        - unknown_clusters: List of clusters of unknown speakers (for identification)
        - total_items: Total number of items to validate
        - session_info: Session metadata
    """
    import time
    print(f"\n=== Building Validation Queue ===")

    # Load already-validated items to skip them
    already_validated = load_already_validated_items()
    if already_validated:
        print(f"  Found {len(already_validated)} already-validated items (will skip)")

    # Pre-build lookup tables to avoid N+1 queries
    print("  Loading unlabeled meetings...")
    t0 = time.time()
    unlabeled_meetings = {
        m.recording_id: m
        for m in data_loader.get_unlabeled_meetings(USER_ID)
    }
    print(f"  Found {len(unlabeled_meetings)} unlabeled meetings ({time.time() - t0:.1f}s)")

    # Build recording cache
    recording_cache = {}

    # Group by suggested participant
    participant_groups = {}
    suggest_count = 0
    skipped_count = 0
    already_done_count = 0
    already_labeled_count = 0  # Recordings that already have speaker labels
    queue_start = time.time()

    for result in results:
        for match in result.speaker_matches:
            # Only include "suggest" status items
            if match.status != "suggest":
                skipped_count += 1
                continue

            pid = match.matched_participant_id
            if not pid:
                skipped_count += 1
                continue

            # Skip already-validated items
            item_id = f"{result.recording_id}::{match.speaker_label}"
            if item_id in already_validated:
                already_done_count += 1
                continue

            suggest_count += 1

            if pid not in participant_groups:
                participant_groups[pid] = {
                    'participant_id': pid,
                    'participant_name': match.matched_display_name,
                    'items': []
                }

            # Get recording details (with caching)
            recording = recording_cache.get(result.recording_id)
            if recording is None:
                t1 = time.time()
                recording = data_loader.get_recording_by_id(result.recording_id, USER_ID)
                recording_cache[result.recording_id] = recording
                rec_time = time.time() - t1
                if rec_time > 0.5:
                    print(f"    Recording fetch took {rec_time:.1f}s for {result.recording_id[:8]}...")

            # Get speaker segments for this match (using pre-built lookup)
            meeting = unlabeled_meetings.get(result.recording_id)

            if not meeting:
                # Recording already has speaker labels (was filtered out of unlabeled_meetings)
                already_labeled_count += 1
                continue

            speaker_segments = [s for s in meeting.speaker_segments
                               if s.speaker_label == match.speaker_label]

            # Get audio URL (this downloads audio if not cached)
            t1 = time.time()
            audio_info = get_audio_url(recording, speaker_segments) if recording else None
            audio_time = time.time() - t1
            if audio_time > 1.0:
                print(f"    Audio download took {audio_time:.1f}s for {result.recording_id[:8]}...")

            total_duration = sum(s.end_s - s.start_s for s in speaker_segments)

            participant_groups[pid]['items'].append({
                'item_id': f"{result.recording_id}::{match.speaker_label}",
                'recording_id': result.recording_id,
                'recording_title': result.title,
                'speaker_label': match.speaker_label,
                'similarity': match.similarity,
                'segment_count': match.segment_count,
                'total_duration': match.total_duration_s,
                'audio': audio_info
            })

    # Sort items within each participant by similarity (highest first)
    for pid, group in participant_groups.items():
        group['items'].sort(key=lambda x: x['similarity'], reverse=True)

    # Convert to list, filter out empty participants, and sort by total items
    participants = [p for p in participant_groups.values() if p['items']]
    participants.sort(key=lambda x: len(x['items']), reverse=True)

    total_items = sum(len(p['items']) for p in participants)

    print(f"\n=== Queue Building Complete ({time.time() - queue_start:.1f}s processing) ===")
    print(f"  Processed: {suggest_count} 'suggest' matches")
    print(f"  Skipped: {skipped_count} (auto/unknown status or no participant)")
    if already_labeled_count > 0:
        print(f"  Already labeled in DB: {already_labeled_count} (skipped - recordings have speaker_mapping)")
    if already_done_count > 0:
        print(f"  Already validated this session: {already_done_count} (skipped)")
    print(f"  Unique participants: {len(participants)}")
    print(f"  Total validation items: {total_items}")

    if total_items == 0:
        print(f"\n⚠️  NO ITEMS TO VALIDATE!")
        print(f"  This means all speaker matches are either:")
        print(f"    - 'auto' (>= 0.78 similarity) - already assigned")
        print(f"    - 'unknown' (< 0.68 similarity) - too low to suggest")
        print(f"  Try adjusting thresholds in app.py (high_threshold/low_threshold) if you want to validate more.")

    # Process unknown speaker clusters
    processed_clusters = []
    if clusters:
        print(f"\n=== Processing {len(clusters)} Unknown Speaker Clusters ===")
        for cluster in clusters:
            # Skip already-validated items in cluster
            filtered_items = []
            for item in cluster['items']:
                item_id = item['key']
                if item_id not in already_validated:
                    filtered_items.append(item)

            if not filtered_items:
                continue  # All items in this cluster already validated

            # Get audio info for representative
            rep = cluster['representative']
            rep_recording = recording_cache.get(rep['recording_id'])
            if rep_recording is None:
                rep_recording = data_loader.get_recording_by_id(rep['recording_id'], USER_ID)
                recording_cache[rep['recording_id']] = rep_recording

            rep_meeting = unlabeled_meetings.get(rep['recording_id'])
            rep_audio = None
            if rep_recording and rep_meeting:
                rep_segments = [s for s in rep_meeting.speaker_segments
                               if s.speaker_label == rep['speaker_label']]
                if rep_segments:
                    rep_audio = get_audio_url(rep_recording, rep_segments)

            # Get audio info for all items in cluster
            items_with_audio = []
            for item in filtered_items:
                item_recording = recording_cache.get(item['recording_id'])
                if item_recording is None:
                    item_recording = data_loader.get_recording_by_id(item['recording_id'], USER_ID)
                    recording_cache[item['recording_id']] = item_recording

                item_meeting = unlabeled_meetings.get(item['recording_id'])
                item_audio = None
                if item_recording and item_meeting:
                    item_segments = [s for s in item_meeting.speaker_segments
                                    if s.speaker_label == item['speaker_label']]
                    if item_segments:
                        item_audio = get_audio_url(item_recording, item_segments)

                items_with_audio.append({
                    'item_id': item['key'],
                    'recording_id': item['recording_id'],
                    'recording_title': item['title'],
                    'speaker_label': item['speaker_label'],
                    'segment_count': item['segment_count'],
                    'total_duration': item['total_duration_s'],
                    'audio': item_audio
                })

            processed_clusters.append({
                'cluster_id': cluster['cluster_id'],
                'size': len(items_with_audio),
                'representative': {
                    'item_id': rep['key'],
                    'recording_id': rep['recording_id'],
                    'recording_title': rep['title'],
                    'speaker_label': rep['speaker_label'],
                    'segment_count': rep['segment_count'],
                    'total_duration': rep['total_duration_s'],
                    'audio': rep_audio
                },
                'items': items_with_audio
            })

        print(f"  Processed {len(processed_clusters)} clusters with {sum(len(c['items']) for c in processed_clusters)} total items")

    total_cluster_items = sum(len(c['items']) for c in processed_clusters)

    return {
        'participants': participants,
        'unknown_clusters': processed_clusters,
        'total_items': total_items,
        'total_cluster_items': total_cluster_items,
        'session_info': {
            'created_at': datetime.now().isoformat(),
            'user_id': USER_ID,
            'items_per_session': 30
        }
    }


# Routes

@app.route('/')
def index():
    """Serve the main HTML page."""
    return send_from_directory('.', 'index.html')


@app.route('/components/<path:filename>')
def serve_components(filename):
    """Serve component files."""
    return send_from_directory('components', filename)


@app.route('/primereact-standalone-bundle.umd.js')
def serve_primereact_bundle():
    """Serve the PrimeReact bundle."""
    return send_from_directory('.', 'primereact-standalone-bundle.umd.js')


@app.route('/audio/<path:filename>')
def serve_audio(filename):
    """Serve cached audio files."""
    return send_from_directory(AUDIO_CACHE_DIR, filename)


@app.route('/api/validation-queue')
def get_validation_queue():
    """
    Get the validation queue.

    Query params:
        - reload: If 'true', reload from database
        - max_meetings: Maximum meetings to process (default: 10 for testing)
        - cluster_threshold: Similarity threshold for clustering (default: 0.70)
    """
    global validation_queue, embeddings_data

    reload = request.args.get('reload', 'false').lower() == 'true'
    max_meetings = request.args.get('max_meetings', type=int, default=None)  # None = all recordings
    cluster_threshold = request.args.get('cluster_threshold', type=float, default=0.70)

    print(f"\n>>> Processing {'all' if max_meetings is None else f'max {max_meetings}'} meetings (add ?max_meetings=N to URL to limit)")

    if validation_queue is None or reload:
        results = load_identification_results(max_meetings=max_meetings)

        # Cluster unknown speakers
        clusters = []
        if embeddings_data:
            clusters = cluster_unknown_speakers(results, embeddings_data, similarity_threshold=cluster_threshold)

        validation_queue = build_validation_queue(results, clusters=clusters)

    return jsonify(validation_queue)


import fcntl
import tempfile


def get_validation_filepath():
    """Get the current day's validation file path."""
    date_str = datetime.now().strftime('%Y%m%d')
    filename = f'validation-{USER_ID}-{date_str}.json'
    return os.path.join(VALIDATIONS_DIR, filename), filename


def atomic_write_json(filepath: str, data: dict):
    """Write JSON atomically using temp file + rename."""
    # Write to temp file first
    dir_path = os.path.dirname(filepath)
    with tempfile.NamedTemporaryFile(mode='w', dir=dir_path, suffix='.tmp', delete=False) as f:
        json.dump(data, f, indent=2)
        temp_path = f.name
    # Atomic rename
    os.rename(temp_path, filepath)


def locked_read_modify_write(filepath: str, modify_fn):
    """Read-modify-write with file locking to prevent race conditions."""
    # Ensure file exists
    if not os.path.exists(filepath):
        session_data = {
            'validator_id': USER_ID,
            'created_at': datetime.now().isoformat(),
            'decisions': []
        }
        atomic_write_json(filepath, session_data)

    # Open for read/write with exclusive lock
    with open(filepath, 'r+') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            session_data = json.load(f)
            session_data = modify_fn(session_data)
            session_data['updated_at'] = datetime.now().isoformat()
            # Write atomically
            atomic_write_json(filepath, session_data)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    return session_data


@app.route('/api/save-decision', methods=['POST'])
def save_decision():
    """
    Save a single decision immediately (incremental save).
    Appends to a session file for the current day.
    """
    data = request.json
    if not data:
        return jsonify({'error': 'Missing decision data'}), 400

    filepath, filename = get_validation_filepath()

    def add_decision(session_data):
        session_data['decisions'].append(data)
        return session_data

    session_data = locked_read_modify_write(filepath, add_decision)

    return jsonify({'success': True, 'filename': filename, 'total_decisions': len(session_data['decisions'])})


@app.route('/api/remove-decision', methods=['POST'])
def remove_decision():
    """
    Remove a decision (for undo functionality).
    Removes the most recent decision matching the item_id.
    """
    data = request.json
    if not data or 'item_id' not in data:
        return jsonify({'error': 'Missing item_id'}), 400

    filepath, filename = get_validation_filepath()

    if not os.path.exists(filepath):
        return jsonify({'success': True, 'message': 'No decisions file exists'})

    def remove_last_matching(session_data):
        item_id = data['item_id']
        # Find and remove the last decision with this item_id
        for i in range(len(session_data['decisions']) - 1, -1, -1):
            if session_data['decisions'][i].get('item_id') == item_id:
                session_data['decisions'].pop(i)
                break
        return session_data

    session_data = locked_read_modify_write(filepath, remove_last_matching)

    return jsonify({'success': True, 'filename': filename, 'total_decisions': len(session_data['decisions'])})


@app.route('/api/save-session', methods=['POST'])
def save_session():
    """
    Save validation decisions to JSON file.

    Request body:
        {
            "decisions": [
                {
                    "item_id": "recording_id::speaker_label",
                    "decision": "confirmed" | "rejected" | "skipped",
                    "participant_id": "...",
                    "similarity": 0.75
                }
            ],
            "session_metadata": {
                "started_at": "...",
                "completed_at": "...",
                "items_validated": 30
            }
        }
    """
    data = request.json

    if not data or 'decisions' not in data:
        return jsonify({'error': 'Missing decisions'}), 400

    # Create timestamped filename
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    filename = f'validation-{USER_ID}-{timestamp}.json'
    filepath = os.path.join(VALIDATIONS_DIR, filename)

    # Add metadata
    output = {
        'validator_id': USER_ID,
        'validated_at': datetime.now().isoformat(),
        'session_metadata': data.get('session_metadata', {}),
        'decisions': data['decisions']
    }

    # Save to file
    with open(filepath, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n✓ Saved {len(data['decisions'])} validation decisions to {filename}")

    return jsonify({
        'success': True,
        'filename': filename,
        'decisions_saved': len(data['decisions'])
    })


@app.route('/api/reference-audio/<participant_id>')
def get_reference_audio(participant_id):
    """
    Get reference audio samples for a participant.

    Returns 2-3 high-confidence samples from different recordings.
    """
    try:
        if not profile_db:
            return jsonify({'error': 'Profile database not initialized', 'samples': []}), 200

        profile = profile_db.get(participant_id)
        if not profile:
            # Return empty samples instead of 404 to not break UI
            return jsonify({'participant_id': participant_id, 'participant_name': 'Unknown', 'samples': []})

        # Get recordings this participant appears in
        reference_samples = []

        for recording_id in profile.recording_ids[:3]:  # Max 3 samples
            try:
                recording = data_loader.get_recording_by_id(recording_id, USER_ID)
                if not recording:
                    continue

                # Find speaker segments for this participant in this recording
                transcription = data_loader.get_transcription(recording_id, USER_ID)
                if not transcription:
                    continue

                # Find the speaker label that matches this participant
                speaker_label = None
                speakers = transcription.get('speakers') or {}
                for label, speaker_info in speakers.items():
                    if isinstance(speaker_info, dict) and speaker_info.get('participant_id') == participant_id:
                        speaker_label = label
                        break

                if not speaker_label:
                    continue

                # Get segments
                segments = transcription.get('segments') or []
                speaker_segments = [s for s in segments
                           if isinstance(s, dict) and s.get('speaker') == speaker_label]

                if not speaker_segments:
                    continue

                # Find longest segment
                longest = max(speaker_segments, key=lambda s: s.get('end_s', 0) - s.get('start_s', 0))

                # Get audio URL
                audio_path = data_loader.download_audio(recording, AUDIO_CACHE_DIR)

                # Get relative path from cache dir
                cache_dir = os.path.abspath(AUDIO_CACHE_DIR)
                abs_audio_path = os.path.abspath(audio_path)
                relative_path = os.path.relpath(abs_audio_path, cache_dir)

                reference_samples.append({
                    'recording_id': recording_id,
                    'recording_title': recording.title or recording.original_filename,
                    'audio': {
                        'url': f'/audio/{relative_path}',
                        'start': longest.get('start_s', 0),
                        'end': min(longest.get('end_s', 8), longest.get('start_s', 0) + 8.0)
                    }
                })
            except Exception as e:
                print(f"Error getting reference audio for {recording_id}: {e}")
                continue

        return jsonify({
            'participant_id': participant_id,
            'participant_name': profile.display_name,
            'samples': reference_samples
        })
    except Exception as e:
        print(f"Error in reference-audio endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'participant_id': participant_id, 'participant_name': 'Unknown', 'samples': []})


@app.route('/api/participants', methods=['GET'])
def get_participants():
    """Get all participants for the current user."""
    global data_loader
    try:
        # Initialize data_loader if needed (may be called before queue is loaded)
        if data_loader is None:
            data_loader = DataLoader()
        participants = data_loader.get_all_participants(USER_ID)
        return jsonify({
            'participants': [
                {
                    'id': p.id,
                    'displayName': getattr(p, 'displayName', None) or p.id,
                    'firstName': getattr(p, 'firstName', None) or '',
                    'lastName': getattr(p, 'lastName', None) or '',
                    'email': getattr(p, 'email', None) or '',
                    'isUser': getattr(p, 'isUser', False)
                }
                for p in participants
            ]
        })
    except Exception as e:
        print(f"Error getting participants: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/create-participant', methods=['POST'])
def create_participant():
    """
    Create a new participant using the ParticipantHandler.

    Request body:
        {
            "displayName": "John Smith",
            "firstName": "John",  # optional
            "lastName": "Smith"   # optional
        }
    """
    global data_loader
    data = request.json
    if not data or 'displayName' not in data:
        return jsonify({'error': 'Missing displayName'}), 400

    display_name = data['displayName'].strip()
    if not display_name:
        return jsonify({'error': 'displayName cannot be empty'}), 400

    try:
        # Initialize data_loader if needed
        if data_loader is None:
            data_loader = DataLoader()
        # Use the participant handler to create the participant
        participant = data_loader.participant_handler.create_participant(
            user_id=USER_ID,
            displayName=display_name,
            firstName=data.get('firstName', ''),
            lastName=data.get('lastName', '')
        )

        print(f"✓ Created participant: {participant.displayName} ({participant.id})")

        return jsonify({
            'success': True,
            'participant': {
                'id': participant.id,
                'displayName': participant.displayName
            }
        })
    except Exception as e:
        print(f"Error creating participant: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/identify-cluster', methods=['POST'])
def identify_cluster():
    """
    Identify a cluster of unknown speakers as a participant.

    This assigns the participant to the cluster and returns
    all items in the cluster for confirmation.

    Request body:
        {
            "cluster_id": "cluster-0",
            "participant_id": "uuid-...",
            "participant_name": "John Smith"  # for display
        }
    """
    data = request.json
    if not data:
        return jsonify({'error': 'Missing request body'}), 400

    cluster_id = data.get('cluster_id')
    participant_id = data.get('participant_id')
    participant_name = data.get('participant_name')

    if not cluster_id or not participant_id:
        return jsonify({'error': 'Missing cluster_id or participant_id'}), 400

    # Find the cluster in the validation queue
    if not validation_queue or 'unknown_clusters' not in validation_queue:
        return jsonify({'error': 'No clusters available'}), 404

    cluster = None
    for c in validation_queue['unknown_clusters']:
        if c['cluster_id'] == cluster_id:
            cluster = c
            break

    if not cluster:
        return jsonify({'error': f'Cluster {cluster_id} not found'}), 404

    print(f"✓ Identified cluster {cluster_id} ({cluster['size']} items) as {participant_name}")

    # Return the cluster items for confirmation
    # The frontend will show these as validation cards
    return jsonify({
        'success': True,
        'cluster_id': cluster_id,
        'participant_id': participant_id,
        'participant_name': participant_name,
        'items': cluster['items']
    })


if __name__ == '__main__':
    if not USER_ID:
        print("Error: QUICKSCRIBE_USER_ID environment variable not set")
        print("\nUsage:")
        print("  export QUICKSCRIBE_USER_ID='your_user_id'")
        print("  export SPEAKER_PROFILES_PATH='../speaker_profiles.json'  # optional")
        print("  python app.py")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("SPEAKER IDENTIFICATION VALIDATION UI")
    print("=" * 70)
    print(f"\nUser ID: {USER_ID}")
    print(f"Profiles: {PROFILES_PATH}")
    print("\nServer starting at http://localhost:5001")
    print("\nPress Ctrl+C to stop\n")

    app.run(debug=True, port=5001)
