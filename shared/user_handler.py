from azure.cosmos import CosmosClient
from datetime import datetime
import uuid

class UserHandler:
    def __init__(self, cosmos_url, cosmos_key, database_name, container_name):
        self.client = CosmosClient(cosmos_url, credential=cosmos_key)
        self.database = self.client.get_database_client(database_name)
        self.container = self.database.get_container_client(container_name)

    def create_user(self, email, name, role="user"):
        """Create a new user in Cosmos DB."""
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
        return user_id

    def get_user(self, user_id):
        """Retrieve a user by ID."""
        try:
            user_item = self.container.read_item(item=user_id, partition_key="user")
            return user_item
        except Exception as e:
            print(f"Error retrieving user: {e}")
            return None

    def get_user_by_name(self, name):
        """Retrieve a user by name."""
        query = "SELECT * FROM c WHERE c.name = @name"
        parameters = [{"name": "@name", "value": name}]
        users = list(self.container.query_items(query=query, parameters=parameters, partition_key="user"))
        return users

    def get_all_users(self):
        """Retrieve all users."""
    
        users = list(self.container.query_items(
            query="SELECT * FROM c",
            partition_key="user"
        ))
        return users

    def update_user(self, user_id, email=None, name=None, role=None):
        """Update user details like email, name, and role."""
        try:
            user_item = self.get_user(user_id)
            if user_item:
                if email:
                    user_item['email'] = email
                if name:
                    user_item['name'] = name
                if role:
                    user_item['role'] = role
                user_item['updated_at'] = datetime.utcnow().isoformat()

                # Update item in Cosmos DB
                self.container.replace_item(item=user_id, body=user_item)
                return user_item
            return None
        except Exception as e:
            print(f"Error updating user: {e}")
            return None

    def delete_user(self, user_id):
        """Delete a user from Cosmos DB."""
        try:
            self.container.delete_item(item=user_id, partition_key="user")
            print(f"User {user_id} deleted successfully.")
        except Exception as e:
            print(f"Error deleting user: {e}")

    def get_user_files(self, user_id):
        """Get all recordings (files) associated with the user."""
        query = "SELECT * FROM c WHERE c.user_id = @user_id AND c.partitionKey = 'recording'"
        parameters = [{"name": "@user_id", "value": user_id}]
        recordings = list(self.container.query_items(query=query, parameters=parameters, enable_cross_partition_query=True))
        return recordings

    def get_user_transcriptions(self, user_id):
        """Get all transcriptions associated with the user."""
        query = "SELECT * FROM c WHERE c.user_id = @user_id AND c.partitionKey = 'transcription'"
        parameters = [{"name": "@user_id", "value": user_id}]
        transcriptions = list(self.container.query_items(query=query, parameters=parameters, enable_cross_partition_query=True))
        return transcriptions
