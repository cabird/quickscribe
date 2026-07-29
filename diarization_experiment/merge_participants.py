#!/usr/bin/env python3
"""
Merge duplicate participants and update names.
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv()

from shared_quickscribe_py.config import get_settings
from azure.cosmos import CosmosClient

settings = get_settings()
client = CosmosClient(settings.cosmos.endpoint, settings.cosmos.key)
db = client.get_database_client(settings.cosmos.database_name)
participants_container = db.get_container_client('participants')
main_container = db.get_container_client('QuickScribeContainer')

USER_ID = "user-bd639cf9-a105-44f5-80e0-478a8ec2e5c2"


def get_participant(pid):
    """Get a participant by ID."""
    items = list(participants_container.query_items(
        query=f"SELECT * FROM c WHERE c.id = '{pid}'",
        enable_cross_partition_query=True
    ))
    return items[0] if items else None


def update_participant(pid, updates):
    """Update a participant record."""
    participant = get_participant(pid)
    if not participant:
        print(f"  ERROR: Participant {pid} not found")
        return False

    for key, value in updates.items():
        participant[key] = value

    participants_container.upsert_item(participant)
    print(f"  Updated participant {pid}: {updates}")
    return True


def delete_participant(pid):
    """Delete a participant record."""
    participant = get_participant(pid)
    if not participant:
        print(f"  WARNING: Participant {pid} not found for deletion")
        return False

    partition_key = participant.get('partitionKey') or participant.get('userId') or USER_ID
    participants_container.delete_item(item=pid, partition_key=partition_key)
    print(f"  Deleted participant {pid}")
    return True


def update_transcriptions_speaker_mapping(old_pid, new_pid, new_display_name):
    """Update all transcriptions that reference old_pid in speaker_mapping."""
    # Find transcriptions with speaker_mapping
    transcriptions = list(main_container.query_items(
        query="""
        SELECT * FROM c
        WHERE IS_DEFINED(c.speaker_mapping) AND c.speaker_mapping != null
        """,
        enable_cross_partition_query=True
    ))

    updated_count = 0
    for trans in transcriptions:
        modified = False
        speaker_mapping = trans.get('speaker_mapping', {})

        for speaker_label, mapping in speaker_mapping.items():
            if isinstance(mapping, dict) and mapping.get('participantId') == old_pid:
                mapping['participantId'] = new_pid
                mapping['displayName'] = new_display_name
                if 'name' in mapping:
                    mapping['name'] = new_display_name
                modified = True

        if modified:
            main_container.upsert_item(trans)
            updated_count += 1
            print(f"    Updated transcription: {trans['id'][:30]}...")

    return updated_count


def merge_participants(keep_id, delete_id, new_display_name):
    """Merge two participants by updating all references and deleting the duplicate.

    Only updates transcription.speaker_mapping (not recording.participants).
    """
    print(f"\n  Merging {delete_id} -> {keep_id}")

    # Update transcriptions (canonical source for speaker->participant mappings)
    trans_count = update_transcriptions_speaker_mapping(delete_id, keep_id, new_display_name)
    print(f"  Updated {trans_count} transcriptions")

    # Delete the old participant
    delete_participant(delete_id)

    return trans_count


def main():
    print("=" * 60)
    print("PARTICIPANT MERGE AND UPDATE SCRIPT")
    print("=" * 60)
    print("\nNote: Only updates participant records and transcription.speaker_mapping")
    print("      (recording.participants is deprecated and not updated)")

    # 1. Update Chris Bird (the main Chris)
    print("\n1. Updating Chris Bird...")
    chris_bird_id = "ae3687a4-ef06-4a8d-8a0b-3f8de757aeab"
    update_participant(chris_bird_id, {
        'displayName': 'Chris Bird',
        'firstName': 'Chris',
        'lastName': 'Bird'
    })

    # 2. Update Chris White -> Chris W.
    print("\n2. Updating Chris White -> Chris W...")
    chris_white_id = "ac56d61f-a061-40db-a5c0-7c8d9dca1b8b"
    # First get the full ID
    chris_entries = list(participants_container.query_items(
        query="SELECT c.id, c.displayName FROM c WHERE CONTAINS(c.displayName, 'Chris')",
        enable_cross_partition_query=True
    ))
    for c in chris_entries:
        if c['displayName'] == 'Chris White':
            chris_white_id = c['id']
            break

    update_participant(chris_white_id, {
        'displayName': 'Chris W.',
        'firstName': 'Chris',
        'lastName': 'White'
    })

    # 3. Merge Darren entries
    print("\n3. Merging Darren entries...")
    darren_keep = "8f2c55a4-0057-48d8-a5a8-67856c543ce3"
    darren_delete = "184a7063-b5e6-4925-afaf-087bc9dd9f94"
    update_participant(darren_keep, {
        'displayName': 'Darren Edge',
        'firstName': 'Darren',
        'lastName': 'Edge'
    })
    merge_participants(darren_keep, darren_delete, 'Darren Edge')

    # 4. Merge Tom entries
    print("\n4. Merging Tom entries...")
    tom_keep = "f2f424de-28fe-425e-b07c-771003c415f3"
    tom_delete = "82120fb3-da49-4ba6-b95c-56c78d12719e"
    update_participant(tom_keep, {
        'displayName': 'Tom Zimmermann',
        'firstName': 'Tom',
        'lastName': 'Zimmermann'
    })
    merge_participants(tom_keep, tom_delete, 'Tom Zimmermann')

    # 5. Merge Madeline/Madline entries
    print("\n5. Merging Madeline/Madline entries...")
    # Get the IDs
    madeline_entries = list(participants_container.query_items(
        query="SELECT c.id, c.displayName FROM c WHERE CONTAINS(LOWER(c.displayName), 'madel') OR CONTAINS(LOWER(c.displayName), 'madli')",
        enable_cross_partition_query=True
    ))
    madeline_keep = None
    madline_delete = None
    for m in madeline_entries:
        if m['displayName'] == 'Madeline':
            madeline_keep = m['id']
        elif m['displayName'] == 'Madline':
            madline_delete = m['id']

    if madeline_keep and madline_delete:
        merge_participants(madeline_keep, madline_delete, 'Madeline')
    else:
        print(f"  WARNING: Could not find both Madeline entries. Keep={madeline_keep}, Delete={madline_delete}")

    print("\n" + "=" * 60)
    print("DONE!")
    print("=" * 60)


if __name__ == "__main__":
    main()
