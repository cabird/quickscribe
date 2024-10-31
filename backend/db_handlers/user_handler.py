from azure.cosmos import CosmosClient
from datetime import datetime
import uuid
from db_handlers.models import User, Recording, Transcription  # Import the Pydantic models
from db_handlers.util import filter_cosmos_fields  # Import the utility function
from typing import Optional, List

class UserHandler:
    def __init__(self, cosmos_url: str, cosmos_key: str, database_name: str, container_name: str):
        self.client = CosmosClient(cosmos_url, credential=cosmos_key)
        self.database = self.client.get_database_client(database_name)
        self.container = self.database.get_container_client(container_name)

    def create_user(self, email: str, name: str, role: str = "user") -> str:
        """Create a new user in Cosmos DB and return the user ID."""
        user_id = f"user-{str(uuid.uuid4())}"
        user_item = {
            "id": user_id,
            "email": email,
            "name": name,
            "role": role,
            "created_at": datetime.utcnow().isoformat(),
            "last_login": None,  # Initialize last_login as None
            "partitionKey": "user"
        }
        self.container.create_item(body=user_item)
        return User(**filter_cosmos_fields(user_item))

    def get_user(self, user_id: str) -> Optional[User]:
        """Retrieve a user by ID and return as a User model."""
        try:
            user_item = self.container.read_item(item=user_id, partition_key="user")
            return User(**filter_cosmos_fields(user_item))
        except Exception as e:
            print(f"Error retrieving user: {e}")
            return None

    def get_user_by_name(self, name: str) -> List[User]:
        """Retrieve a user by name and return as a list of User models."""
        query = "SELECT * FROM c WHERE c.name = @name"
        parameters = [{"name": "@name", "value": name}]
        users = list(self.container.query_items(query=query, parameters=parameters, partition_key="user"))
        return [User(**filter_cosmos_fields(user)) for user in users]

    def get_all_users(self) -> List[User]:
        """Retrieve all users and return as a list of User models."""
        users = list(self.container.query_items(
            query="SELECT * FROM c WHERE c.partitionKey = 'user'",
            partition_key="user"
        ))
        return [User(**filter_cosmos_fields(user)) for user in users]

    def update_user(self, user_id: str, email: Optional[str] = None, name: Optional[str] = None, role: Optional[str] = None) -> Optional[User]:
        """Update user details like email, name, and role, and return the updated User model."""
        try:
            user_item = self.get_user(user_id)
            if user_item:
                user_data = user_item.model_dump()  
                if email:
                    user_data['email'] = email
                if name:
                    user_data['name'] = name
                if role:
                    user_data['role'] = role
                user_data['updated_at'] = datetime.utcnow().isoformat()

                # Update item in Cosmos DB
                updated_item = self.container.replace_item(item=user_id, body=user_data)
                return User(**filter_cosmos_fields(updated_item))
            return None
        except Exception as e:
            print(f"Error updating user: {e}")
            return None

    def delete_user(self, user_id: str) -> None:
        """Delete a user from Cosmos DB."""
        try:
            self.container.delete_item(item=user_id, partition_key="user")
            print(f"User {user_id} deleted successfully.")
        except Exception as e:
            print(f"Error deleting user: {e}")

    def get_user_files(self, user_id: str) -> List[Recording]:
        """Get all recordings (files) associated with the user and return as Recording models."""
        query = "SELECT * FROM c WHERE c.user_id = @user_id AND c.partitionKey = 'recording'"
        parameters = [{"name": "@user_id", "value": user_id}]
        recordings = list(self.container.query_items(query=query, parameters=parameters, enable_cross_partition_query=True))
        return [Recording(**filter_cosmos_fields(recording)) for recording in recordings]

    def get_user_transcriptions(self, user_id: str) -> List[Transcription]:
        """Get all transcriptions associated with the user and return as Transcription models."""
        query = "SELECT * FROM c WHERE c.user_id = @user_id AND c.partitionKey = 'transcription'"
        parameters = [{"name": "@user_id", "value": user_id}]
        transcriptions = list(self.container.query_items(query=query, parameters=parameters, enable_cross_partition_query=True))
        return [Transcription(**filter_cosmos_fields(transcription)) for transcription in transcriptions]
