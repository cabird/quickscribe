"""
Participant database handler for CosmosDB operations.
Manages participant profiles as first-class entities.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import uuid4
from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from pydantic import ValidationError, field_validator, field_serializer

from .models import Participant as BaseParticipant

logger = logging.getLogger(__name__)

class Participant(BaseParticipant):
    """Extended Participant model with datetime handling."""
    
    @field_validator('firstSeen', 'lastSeen', 'createdAt', 'updatedAt', mode='before')
    @classmethod
    def parse_datetime(cls, v):
        """Parse datetime values from CosmosDB."""
        if v is None:
            return None
        if isinstance(v, datetime):
            # Convert datetime objects to ISO strings for Pydantic
            return v.isoformat()
        if isinstance(v, str):
            # Keep strings as-is (they should be ISO format)
            return v
        return v
    
    @field_serializer('firstSeen', 'lastSeen', 'createdAt', 'updatedAt')
    def serialize_datetime(self, value) -> Optional[str]:
        """Serialize datetime objects to ISO strings for storage."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        return value

class ParticipantHandler:
    """Handler for participant database operations."""

    def __init__(self, cosmos_url: str, cosmos_key: str, database_name: str, container_name: str):
        """
        Initialize the ParticipantHandler with Cosmos DB connection details.

        Args:
            cosmos_url: URL for the Cosmos DB account
            cosmos_key: Key for the Cosmos DB account
            database_name: Name of the database
            container_name: Name of the container
        """
        self.client = CosmosClient(cosmos_url, credential=cosmos_key)
        self.database = self.client.get_database_client(database_name)
        self.container = self.database.get_container_client(container_name)
    
    def create_participant(self, user_id: str, **participant_data) -> Participant:
        """
        Create a new participant profile.
        
        Args:
            user_id: ID of the user creating the participant
            **participant_data: Participant fields (firstName, lastName, displayName, etc.)
            
        Returns:
            Created Participant object
        """
        now = datetime.now(timezone.utc)
        
        # Generate unique ID
        participant_id = str(uuid4())
        
        # Ensure required fields
        if 'displayName' not in participant_data:
            raise ValueError("displayName is required")
        
        # Build participant data with defaults for missing fields
        data = {
            'id': participant_id,
            'type': 'participant',
            'userId': user_id,
            'partitionKey': user_id,
            **participant_data
        }
        
        # Set defaults for optional fields only if not provided
        if 'aliases' not in data:
            data['aliases'] = []
        if 'firstSeen' not in data:
            data['firstSeen'] = now.isoformat()
        if 'lastSeen' not in data:
            data['lastSeen'] = now.isoformat()
        if 'createdAt' not in data:
            data['createdAt'] = now.isoformat()
        if 'updatedAt' not in data:
            data['updatedAt'] = now.isoformat()
        
        try:
            # Save directly to database to avoid datetime serialization issues
            created_item = self.container.create_item(body=data)
            
            logger.info(f"Created participant {participant_id} for user {user_id}")
            
            # Return as Participant object for consistency
            try:
                return Participant(**created_item)
            except ValidationError:
                # Fallback: return base model if extended validation fails
                return BaseParticipant(**created_item)
            
        except ValidationError as e:
            logger.error(f"Validation error creating participant: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating participant: {e}")
            raise
    
    def get_participant(self, user_id: str, participant_id: str) -> Optional[Participant]:
        """
        Get a participant by ID.
        
        Args:
            user_id: ID of the user who owns the participant
            participant_id: ID of the participant
            
        Returns:
            Participant object or None if not found
        """
        try:
            item = self.container.read_item(
                item=participant_id,
                partition_key=user_id
            )
            return Participant(**item)
        except CosmosResourceNotFoundError:
            return None
        except Exception as e:
            logger.error(f"Error fetching participant {participant_id}: {e}")
            raise
    
    def get_participants_for_user(self, user_id: str) -> List[Participant]:
        """
        Get all participants for a user.
        
        Args:
            user_id: ID of the user
            
        Returns:
            List of Participant objects
        """
        try:
            query = "SELECT * FROM c WHERE c.type = 'participant' AND c.userId = @user_id ORDER BY c.displayName"
            parameters = [{"name": "@user_id", "value": user_id}]
            
            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                partition_key=user_id
            ))
            
            return [Participant(**item) for item in items]
            
        except Exception as e:
            logger.error(f"Error fetching participants for user {user_id}: {e}")
            raise
    
    def update_participant(self, user_id: str, participant_id: str, updates: Dict[str, Any]) -> Optional[Participant]:
        """
        Update a participant profile.
        
        Args:
            user_id: ID of the user who owns the participant
            participant_id: ID of the participant
            updates: Dictionary of fields to update
            
        Returns:
            Updated Participant object or None if not found
        """
        try:
            # Get existing participant
            existing = self.get_participant(user_id, participant_id)
            if not existing:
                return None
            
            # Apply updates
            participant_dict = existing.model_dump()
            participant_dict.update(updates)
            participant_dict['updatedAt'] = datetime.now(timezone.utc).isoformat()
            
            # Validate updated data
            updated_participant = Participant(**participant_dict)
            
            # Save to database
            saved_item = self.container.replace_item(
                item=participant_id,
                body=updated_participant.model_dump()
            )
            
            logger.info(f"Updated participant {participant_id}")
            return Participant(**saved_item)
            
        except ValidationError as e:
            logger.error(f"Validation error updating participant {participant_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error updating participant {participant_id}: {e}")
            raise
    
    def delete_participant(self, user_id: str, participant_id: str) -> bool:
        """
        Delete a participant profile.
        
        Args:
            user_id: ID of the user who owns the participant
            participant_id: ID of the participant
            
        Returns:
            True if deleted, False if not found
        """
        try:
            self.container.delete_item(
                item=participant_id,
                partition_key=user_id
            )
            logger.info(f"Deleted participant {participant_id}")
            return True
            
        except CosmosResourceNotFoundError:
            return False
        except Exception as e:
            logger.error(f"Error deleting participant {participant_id}: {e}")
            raise
    
    def find_participants_by_name(self, user_id: str, name: str, fuzzy: bool = True) -> List[Participant]:
        """
        Find participants by name or alias.
        
        Args:
            user_id: ID of the user
            name: Name to search for
            fuzzy: Whether to use fuzzy matching (contains)
            
        Returns:
            List of matching Participant objects
        """
        try:
            if fuzzy:
                # Use CONTAINS for fuzzy matching
                query = """
                SELECT * FROM c
                WHERE c.type = 'participant'
                AND c.userId = @user_id
                AND (
                    CONTAINS(LOWER(c.displayName), LOWER(@name))
                    OR CONTAINS(LOWER(c.firstName), LOWER(@name))
                    OR CONTAINS(LOWER(c.lastName), LOWER(@name))
                    OR EXISTS(SELECT VALUE alias FROM alias IN c.aliases WHERE CONTAINS(LOWER(alias), LOWER(@name)))
                )
                ORDER BY c.displayName
                """
            else:
                # Exact matching
                query = """
                SELECT * FROM c
                WHERE c.type = 'participant'
                AND c.userId = @user_id
                AND (
                    LOWER(c.displayName) = LOWER(@name)
                    OR LOWER(c.firstName) = LOWER(@name)
                    OR LOWER(c.lastName) = LOWER(@name)
                    OR EXISTS(SELECT VALUE alias FROM alias IN c.aliases WHERE LOWER(alias) = LOWER(@name))
                )
                ORDER BY c.displayName
                """
            
            parameters = [
                {"name": "@user_id", "value": user_id},
                {"name": "@name", "value": name}
            ]
            
            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                partition_key=user_id
            ))
            
            return [Participant(**item) for item in items]
            
        except Exception as e:
            logger.error(f"Error searching participants for user {user_id} with name '{name}': {e}")
            raise
    
    def save_participant(self, participant: Participant) -> Participant:
        """
        Save a participant object to the database.
        
        Args:
            participant: Participant object to save
            
        Returns:
            Saved Participant object
        """
        try:
            participant_dict = participant.model_dump()
            saved_item = self.container.upsert_item(body=participant_dict)
            
            logger.info(f"Saved participant {participant.id}")
            return Participant(**saved_item)
            
        except Exception as e:
            logger.error(f"Error saving participant {participant.id}: {e}")
            raise
    
    def update_participant_last_seen(self, user_id: str, participant_id: str, timestamp: Optional[datetime] = None) -> bool:
        """
        Update the lastSeen timestamp for a participant.
        
        Args:
            user_id: ID of the user who owns the participant
            participant_id: ID of the participant
            timestamp: Timestamp to set (defaults to now)
            
        Returns:
            True if updated successfully
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        return bool(self.update_participant(user_id, participant_id, {
            'lastSeen': timestamp.isoformat()
        }))