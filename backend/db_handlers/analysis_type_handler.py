from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from datetime import datetime, UTC
import uuid
from db_handlers import models
from db_handlers.models import AnalysisType  # Import the Pydantic models
from db_handlers.util import filter_cosmos_fields  # Import the utility function
from typing import Optional, List, Dict, Any
from pydantic import field_validator, field_serializer


class AnalysisType(models.AnalysisType):
    """Extended AnalysisType model with datetime handling"""
    
    # Override the datetime fields to use actual datetime objects
    createdAt: datetime
    updatedAt: datetime
    
    @field_validator('createdAt', 'updatedAt', mode='before')
    @classmethod
    def parse_datetime(cls, v):
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace('Z', '+00:00'))
        raise ValueError(f"Cannot parse datetime from {type(v)}")
    
    @field_serializer('createdAt', 'updatedAt')
    def serialize_datetime(self, value) -> str:
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)


class AnalysisTypeHandler:
    def __init__(self, cosmos_url: str, cosmos_key: str, database_name: str, container_name: str):
        self.client = CosmosClient(cosmos_url, credential=cosmos_key)
        self.database = self.client.get_database_client(database_name)
        self.container = self.database.get_container_client(container_name)

    def get_analysis_types_for_user(self, user_id: str) -> List[AnalysisType]:
        """Get all analysis types available to a user (built-in + user's custom types)."""
        try:
            # Query for built-in types (global partition)
            builtin_query = "SELECT * FROM c WHERE c.partitionKey = 'global' AND c.isActive = true"
            builtin_types = list(self.container.query_items(
                query=builtin_query,
                partition_key="global"
            ))
            
            # Query for user's custom types
            custom_query = "SELECT * FROM c WHERE c.partitionKey = @user_id AND c.isActive = true"
            custom_params = [{"name": "@user_id", "value": user_id}]
            custom_types = list(self.container.query_items(
                query=custom_query,
                parameters=custom_params,
                partition_key=user_id
            ))
            
            # Combine and convert to models
            all_types = builtin_types + custom_types
            
            # Handle legacy data that doesn't have shortTitle
            analysis_types = []
            for item in all_types:
                filtered_item = filter_cosmos_fields(item)
                # Provide default shortTitle if missing (for legacy data)
                if 'shortTitle' not in filtered_item or filtered_item['shortTitle'] is None:
                    filtered_item['shortTitle'] = filtered_item.get('title', 'Unknown')[:12]
                analysis_types.append(AnalysisType(**filtered_item))
            
            return analysis_types
            
        except Exception as e:
            print(f"Error retrieving analysis types for user {user_id}: {e}")
            return []

    def create_analysis_type(self, name: str, title: str, short_title: str, description: str, 
                           icon: str, prompt: str, user_id: str) -> Optional[AnalysisType]:
        """Create a new custom analysis type."""
        try:
            # Check name uniqueness for this user
            if self._is_name_taken(name, user_id):
                raise ValueError(f"Analysis type name '{name}' already exists for this user")
            
            analysis_type_id = str(uuid.uuid4())
            now = datetime.now(UTC)
            
            analysis_type_item = {
                "id": analysis_type_id,
                "name": name,
                "title": title,
                "shortTitle": short_title,
                "description": description,
                "icon": icon,
                "prompt": prompt,
                "userId": user_id,
                "isActive": True,
                "isBuiltIn": False,
                "createdAt": now.isoformat(),
                "updatedAt": now.isoformat(),
                "partitionKey": user_id
            }
            
            created_item = self.container.create_item(body=analysis_type_item)
            return AnalysisType(**filter_cosmos_fields(created_item))
            
        except Exception as e:
            print(f"Error creating analysis type: {e}")
            return None

    def update_analysis_type(self, type_id: str, user_id: str, updates: Dict[str, Any]) -> Optional[AnalysisType]:
        """Update a custom analysis type (user can only update their own)."""
        try:
            # Get existing item to verify ownership
            existing_item = self.container.read_item(item=type_id, partition_key=user_id)
            
            # Verify user ownership and not built-in
            if existing_item.get('userId') != user_id or existing_item.get('isBuiltIn', False):
                raise ValueError("Cannot update this analysis type - insufficient permissions")
            
            # Check name uniqueness if name is being changed
            if 'name' in updates and updates['name'] != existing_item.get('name'):
                if self._is_name_taken(updates['name'], user_id):
                    raise ValueError(f"Analysis type name '{updates['name']}' already exists for this user")
            
            # Update timestamp
            updates['updatedAt'] = datetime.now(UTC).isoformat()
            
            # Merge updates with existing item
            updated_item = {**existing_item, **updates}
            
            replaced_item = self.container.replace_item(item=type_id, body=updated_item)
            return AnalysisType(**filter_cosmos_fields(replaced_item))
            
        except CosmosResourceNotFoundError:
            print(f"Analysis type {type_id} not found for user {user_id}")
            return None
        except Exception as e:
            print(f"Error updating analysis type: {e}")
            return None

    def delete_analysis_type(self, type_id: str, user_id: str) -> bool:
        """Delete a custom analysis type (user can only delete their own)."""
        try:
            # Get existing item to verify ownership
            existing_item = self.container.read_item(item=type_id, partition_key=user_id)
            
            # Verify user ownership and not built-in
            if existing_item.get('userId') != user_id or existing_item.get('isBuiltIn', False):
                raise ValueError("Cannot delete this analysis type - insufficient permissions")
            
            self.container.delete_item(item=type_id, partition_key=user_id)
            return True
            
        except CosmosResourceNotFoundError:
            print(f"Analysis type {type_id} not found for user {user_id}")
            return False
        except Exception as e:
            print(f"Error deleting analysis type: {e}")
            return False

    def get_analysis_type_by_id(self, type_id: str, partition_key: str) -> Optional[AnalysisType]:
        """Get a single analysis type by ID."""
        try:
            item = self.container.read_item(item=type_id, partition_key=partition_key)
            return AnalysisType(**filter_cosmos_fields(item))
        except CosmosResourceNotFoundError:
            return None
        except Exception as e:
            print(f"Error retrieving analysis type {type_id}: {e}")
            return None

    def get_builtin_analysis_types(self) -> List[AnalysisType]:
        """Get all built-in analysis types."""
        try:
            query = "SELECT * FROM c WHERE c.partitionKey = 'global' AND c.isBuiltIn = true AND c.isActive = true"
            items = list(self.container.query_items(
                query=query,
                partition_key="global"
            ))
            
            # Handle legacy data that doesn't have shortTitle
            analysis_types = []
            for item in items:
                filtered_item = filter_cosmos_fields(item)
                # Provide default shortTitle if missing (for legacy data)
                if 'shortTitle' not in filtered_item or filtered_item['shortTitle'] is None:
                    filtered_item['shortTitle'] = filtered_item.get('title', 'Unknown')[:12]
                analysis_types.append(AnalysisType(**filtered_item))
            
            return analysis_types
        except Exception as e:
            print(f"Error retrieving built-in analysis types: {e}")
            return []

    def create_builtin_analysis_type(self, name: str, title: str, short_title: str, 
                                   description: str, icon: str, prompt: str) -> Optional[AnalysisType]:
        """Create a built-in analysis type (admin/seeding use only)."""
        try:
            analysis_type_id = str(uuid.uuid4())
            now = datetime.now(UTC)
            
            analysis_type_item = {
                "id": analysis_type_id,
                "name": name,
                "title": title,
                "shortTitle": short_title,
                "description": description,
                "icon": icon,
                "prompt": prompt,
                "userId": None,
                "isActive": True,
                "isBuiltIn": True,
                "createdAt": now.isoformat(),
                "updatedAt": now.isoformat(),
                "partitionKey": "global"
            }
            
            created_item = self.container.create_item(body=analysis_type_item)
            return AnalysisType(**filter_cosmos_fields(created_item))
            
        except Exception as e:
            print(f"Error creating built-in analysis type: {e}")
            return None

    def _is_name_taken(self, name: str, user_id: str) -> bool:
        """Check if an analysis type name is already taken by this user."""
        try:
            # Check in user's custom types
            custom_query = "SELECT * FROM c WHERE c.partitionKey = @user_id AND c.name = @name"
            custom_params = [
                {"name": "@user_id", "value": user_id},
                {"name": "@name", "value": name}
            ]
            custom_results = list(self.container.query_items(
                query=custom_query,
                parameters=custom_params,
                partition_key=user_id
            ))
            
            # Check in built-in types (global namespace)
            builtin_query = "SELECT * FROM c WHERE c.partitionKey = 'global' AND c.name = @name"
            builtin_params = [{"name": "@name", "value": name}]
            builtin_results = list(self.container.query_items(
                query=builtin_query,
                parameters=builtin_params,
                partition_key="global"
            ))
            
            return len(custom_results) > 0 or len(builtin_results) > 0
            
        except Exception as e:
            print(f"Error checking name uniqueness: {e}")
            return True  # Err on the side of caution