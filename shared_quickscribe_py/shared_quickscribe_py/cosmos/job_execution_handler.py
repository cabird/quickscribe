"""
Handler for JobExecution documents in Cosmos DB.
Manages job execution tracking for Plaud sync service.
"""
from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from typing import Optional, List
from datetime import datetime, UTC

from ..logging.config import get_logger
from .models import JobExecution

logger = get_logger('job_execution.handler')


class JobExecutionHandler:
    """
    Handler for JobExecution operations in Cosmos DB.
    """

    def __init__(self, cosmos_url: str, cosmos_key: str, database_name: str, container_name: str):
        self.client = CosmosClient(cosmos_url, credential=cosmos_key)
        self.database = self.client.get_database_client(database_name)
        self.container = self.database.get_container_client(container_name)

    def create_job_execution(self, job_execution: JobExecution) -> JobExecution:
        """
        Create a new job execution record.

        Args:
            job_execution: JobExecution model to create

        Returns:
            Created JobExecution
        """
        try:
            job_dict = job_execution.model_dump(mode='json')
            job_dict['type'] = 'job_execution'

            created = self.container.create_item(body=job_dict)
            logger.info(f"Created job execution: {job_execution.id}")

            return JobExecution(**created)
        except Exception as e:
            logger.error(f"Error creating job execution {job_execution.id}: {str(e)}")
            raise

    def get_job_execution(self, job_id: str) -> Optional[JobExecution]:
        """
        Get a job execution by ID.

        Args:
            job_id: Job execution ID

        Returns:
            JobExecution if found, None otherwise
        """
        try:
            item = self.container.read_item(item=job_id, partition_key="job_execution")
            return JobExecution(**item)
        except CosmosResourceNotFoundError:
            logger.warning(f"Job execution not found: {job_id}")
            return None
        except Exception as e:
            logger.error(f"Error getting job execution {job_id}: {str(e)}")
            raise

    def update_job_execution(self, job_execution: JobExecution) -> JobExecution:
        """
        Update an existing job execution.

        Args:
            job_execution: JobExecution model with updates

        Returns:
            Updated JobExecution
        """
        try:
            job_dict = job_execution.model_dump(mode='json')
            job_dict['type'] = 'job_execution'

            updated = self.container.upsert_item(body=job_dict)
            logger.info(f"Updated job execution: {job_execution.id}")

            return JobExecution(**updated)
        except Exception as e:
            logger.error(f"Error updating job execution {job_execution.id}: {str(e)}")
            raise

    def get_recent_jobs(self, limit: int = 10) -> List[JobExecution]:
        """
        Get recent job executions, ordered by start time descending.

        Args:
            limit: Maximum number of jobs to return

        Returns:
            List of JobExecution records
        """
        try:
            query = """
            SELECT TOP @limit * FROM c
            WHERE c.type = 'job_execution'
            ORDER BY c.startTime DESC
            """
            parameters = [{"name": "@limit", "value": limit}]

            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                partition_key="job_execution"
            ))

            return [JobExecution(**item) for item in items]
        except Exception as e:
            logger.error(f"Error getting recent jobs: {str(e)}")
            raise

    def get_jobs_by_user(self, user_id: str, limit: int = 10) -> List[JobExecution]:
        """
        Get job executions for a specific user.

        Args:
            user_id: User ID to filter by
            limit: Maximum number of jobs to return

        Returns:
            List of JobExecution records
        """
        try:
            query = """
            SELECT TOP @limit * FROM c
            WHERE c.type = 'job_execution'
            AND c.userId = @user_id
            ORDER BY c.startTime DESC
            """
            parameters = [
                {"name": "@limit", "value": limit},
                {"name": "@user_id", "value": user_id}
            ]

            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                partition_key="job_execution"
            ))

            return [JobExecution(**item) for item in items]
        except Exception as e:
            logger.error(f"Error getting jobs for user {user_id}: {str(e)}")
            raise

    def delete_job_execution(self, job_id: str) -> None:
        """
        Delete a job execution by ID.

        Args:
            job_id: Job execution ID to delete
        """
        try:
            self.container.delete_item(item=job_id, partition_key="job_execution")
            logger.info(f"Deleted job execution: {job_id}")
        except CosmosResourceNotFoundError:
            logger.warning(f"Job execution not found for deletion: {job_id}")
        except Exception as e:
            logger.error(f"Error deleting job execution {job_id}: {str(e)}")
            raise
