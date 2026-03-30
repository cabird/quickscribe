# /// script
# dependencies = [
#     "python-dotenv>=1.0.0",
# ]
# requires-python = ">=3.11"
# ///
"""Normalize speaker_mapping JSON to use camelCase keys only.

Migrates all legacy snake_case and v1 field names to the canonical camelCase format.
Removes deprecated fields: name, reasoning, display_name, participant_id,
manually_verified, identification_status, suggested_participant_id,
suggested_display_name, top_candidates, identified_at, use_for_training.

Usage:
    cd v2/tools && uv run normalize_speaker_mappings.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the backend directory and fix relative DATABASE_PATH
_backend_dir = Path(__file__).resolve().parent.parent / "backend"
load_dotenv(_backend_dir / ".env")

db_path = os.environ.get("DATABASE_PATH", "./data/app.db")
if not os.path.isabs(db_path):
    db_path = str(_backend_dir / db_path)

LEGACY_KEYS = {
    "name", "reasoning", "display_name", "participant_id",
    "manually_verified", "identification_status", "suggested_participant_id",
    "suggested_display_name", "top_candidates", "identified_at",
    "use_for_training",
}


def normalize_candidate(c: dict) -> dict:
    """Normalize a top candidate entry to camelCase only."""
    return {
        "participantId": c.get("participantId") or c.get("participant_id") or "",
        "displayName": c.get("displayName") or c.get("display_name") or "",
        "similarity": c.get("similarity", 0.0),
    }


def normalize_entry(entry: dict, participant_lookup: dict[str, str]) -> dict:
    """Normalize a single speaker mapping entry to camelCase only."""
    # Resolve displayName through fallback chain
    display_name = (
        entry.get("displayName")
        or entry.get("display_name")
        or entry.get("name")
    )
    if not display_name:
        pid = entry.get("participantId") or entry.get("participant_id")
        if pid:
            display_name = participant_lookup.get(pid)

    # Resolve participantId
    participant_id = entry.get("participantId") or entry.get("participant_id")

    # Resolve manuallyVerified
    mv = entry.get("manuallyVerified")
    if mv is None:
        mv = entry.get("manually_verified")
    if mv is None:
        mv = False

    # Resolve identificationStatus
    id_status = entry.get("identificationStatus") or entry.get("identification_status")

    # Resolve suggestedParticipantId
    suggested_pid = entry.get("suggestedParticipantId") or entry.get("suggested_participant_id")

    # Resolve suggestedDisplayName
    suggested_dn = entry.get("suggestedDisplayName") or entry.get("suggested_display_name")

    # Resolve topCandidates
    top_candidates = entry.get("topCandidates") or entry.get("top_candidates")
    if top_candidates and isinstance(top_candidates, list):
        top_candidates = [normalize_candidate(c) for c in top_candidates]

    # Resolve identifiedAt
    identified_at = entry.get("identifiedAt") or entry.get("identified_at")

    # Resolve useForTraining
    uft = entry.get("useForTraining")
    if uft is None:
        uft = entry.get("use_for_training")
    if uft is None:
        uft = False

    result: dict = {
        "participantId": participant_id,
        "displayName": display_name,
        "confidence": entry.get("confidence"),
        "manuallyVerified": mv,
        "identificationStatus": id_status,
        "similarity": entry.get("similarity"),
        "suggestedParticipantId": suggested_pid,
        "suggestedDisplayName": suggested_dn,
        "topCandidates": top_candidates,
        "identifiedAt": identified_at,
        "useForTraining": uft,
    }

    # Keep embedding as-is
    if "embedding" in entry:
        result["embedding"] = entry["embedding"]

    return result


def main(dry_run: bool = False) -> None:
    print(f"Database: {db_path}")
    print(f"Dry run: {dry_run}")
    print()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Load participants into lookup dict
    participant_rows = conn.execute("SELECT id, display_name FROM participants").fetchall()
    participant_lookup = {r["id"]: r["display_name"] for r in participant_rows}
    print(f"Loaded {len(participant_lookup)} participants")

    # Load all recordings with non-null speaker_mapping
    rows = conn.execute(
        "SELECT id, title, original_filename, speaker_mapping FROM recordings WHERE speaker_mapping IS NOT NULL"
    ).fetchall()
    total = len(rows)
    print(f"Found {total} recordings with speaker_mapping\n")

    updated_recordings = 0
    updated_speakers = 0
    batch_count = 0

    for i, row in enumerate(rows, 1):
        rec_id = row["id"]
        title = row["title"] or row["original_filename"]
        raw = row["speaker_mapping"]

        try:
            mapping = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue

        if not isinstance(mapping, dict):
            continue

        speaker_count = 0
        new_mapping = {}
        for label, entry in mapping.items():
            if not isinstance(entry, dict):
                new_mapping[label] = entry
                continue
            new_mapping[label] = normalize_entry(entry, participant_lookup)
            speaker_count += 1

        new_json = json.dumps(new_mapping)
        if new_json != raw:
            updated_recordings += 1
            updated_speakers += speaker_count
            print(f"[{i}/{total}] normalized {speaker_count} speakers in \"{title}\"")

            if not dry_run:
                conn.execute(
                    "UPDATE recordings SET speaker_mapping = ? WHERE id = ?",
                    (new_json, rec_id),
                )
                batch_count += 1
                if batch_count >= 50:
                    conn.commit()
                    batch_count = 0
        else:
            print(f"[{i}/{total}] no changes needed for \"{title}\"")

    if not dry_run and batch_count > 0:
        conn.commit()

    conn.close()

    print(f"\nDone! {updated_recordings} recordings normalized, {updated_speakers} speaker entries updated")
    if dry_run:
        print("(dry run -- no changes written)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Normalize speaker_mapping to camelCase")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
