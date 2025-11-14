"""
Handler for JobExecution documents in Cosmos DB.
Manages job execution tracking for Plaud sync service.
"""
from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from typing import Optional, List, Dict, Any, Tuple
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

    def query_jobs(
        self,
        limit: int = 50,
        offset: int = 0,
        min_duration: Optional[int] = None,
        has_activity: Optional[bool] = None,
        status: Optional[List[str]] = None,
        trigger_source: Optional[str] = None,
        user_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        sort_by: str = "startTime",
        sort_order: str = "desc"
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Query job executions with advanced filtering, pagination, and sorting.

        Args:
            limit: Maximum number of items per page (max 100)
            offset: Number of items to skip
            min_duration: Minimum duration in seconds
            has_activity: Filter for jobs with activity (recordings/transcriptions/errors > 0)
            status: List of statuses to filter by
            trigger_source: Filter by trigger source ('scheduled' or 'manual')
            user_id: Filter by specific user ID
            start_date: ISO timestamp - jobs started after this date
            end_date: ISO timestamp - jobs started before this date
            sort_by: Field to sort by (startTime, endTime, duration, errors)
            sort_order: Sort order ('asc' or 'desc')

        Returns:
            Tuple of (list of job dicts with computed fields, total count)
        """
        try:
            # Enforce max limit
            limit = min(limit, 100)

            # Build WHERE clause conditions
            where_conditions = ["c.type = 'job_execution'"]
            parameters = []

            if status:
                status_placeholders = []
                for idx, s in enumerate(status):
                    param_name = f"@status{idx}"
                    status_placeholders.append(param_name)
                    parameters.append({"name": param_name, "value": s})
                where_conditions.append(f"c.status IN ({', '.join(status_placeholders)})")

            if trigger_source:
                where_conditions.append("c.triggerSource = @trigger_source")
                parameters.append({"name": "@trigger_source", "value": trigger_source})

            if user_id:
                where_conditions.append("c.userId = @user_id")
                parameters.append({"name": "@user_id", "value": user_id})

            if start_date:
                where_conditions.append("c.startTime >= @start_date")
                parameters.append({"name": "@start_date", "value": start_date})

            if end_date:
                where_conditions.append("c.startTime <= @end_date")
                parameters.append({"name": "@end_date", "value": end_date})

            where_clause = " AND ".join(where_conditions)

            # Build ORDER BY clause
            sort_field_map = {
                "startTime": "c.startTime",
                "endTime": "c.endTime",
                "errors": "c.stats.errors"
            }
            sort_field = sort_field_map.get(sort_by, "c.startTime")
            sort_direction = "DESC" if sort_order.lower() == "desc" else "ASC"

            # Query for all matching items (we'll filter client-side for complex conditions)
            query = f"""
            SELECT * FROM c
            WHERE {where_clause}
            ORDER BY {sort_field} {sort_direction}
            """

            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                partition_key="job_execution"
            ))

            # Client-side filtering for complex conditions
            filtered_items = []
            for item in items:
                stats = item.get('stats', {})

                # Filter by has_activity
                if has_activity is not None:
                    recordings = stats.get('recordings_uploaded', 0)
                    transcriptions = stats.get('transcriptions_completed', 0)
                    errors = stats.get('errors', 0)
                    activity = recordings > 0 or transcriptions > 0 or errors > 0

                    if has_activity and not activity:
                        continue
                    if not has_activity and activity:
                        continue

                # Filter by min_duration
                if min_duration is not None:
                    start_time = item.get('startTime')
                    end_time = item.get('endTime')

                    if start_time and end_time:
                        try:
                            start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                            end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                            duration = (end - start).total_seconds()

                            if duration < min_duration:
                                continue
                        except:
                            # Skip items with invalid dates
                            continue
                    else:
                        # Skip items without both timestamps
                        continue

                # Add computed duration field
                start_time = item.get('startTime')
                end_time = item.get('endTime')
                if start_time and end_time:
                    try:
                        start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                        end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                        duration_seconds = int((end - start).total_seconds())
                        item['duration'] = duration_seconds

                        # Add formatted duration
                        minutes = duration_seconds // 60
                        seconds = duration_seconds % 60
                        if minutes > 0:
                            item['durationFormatted'] = f"{minutes}m {seconds}s"
                        else:
                            item['durationFormatted'] = f"{seconds}s"
                    except:
                        item['duration'] = None
                        item['durationFormatted'] = None
                else:
                    item['duration'] = None
                    item['durationFormatted'] = None

                filtered_items.append(item)

            # Sort by duration if requested (needs to be done after computing)
            if sort_by == "duration":
                filtered_items.sort(
                    key=lambda x: x.get('duration') or 0,
                    reverse=(sort_order.lower() == "desc")
                )

            # Get total count
            total_count = len(filtered_items)

            # Apply pagination
            paginated_items = filtered_items[offset:offset + limit]

            return paginated_items, total_count

        except Exception as e:
            logger.error(f"Error querying jobs: {str(e)}")
            raise
