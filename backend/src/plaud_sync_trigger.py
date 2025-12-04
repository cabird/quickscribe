"""
Service for manually triggering the Plaud Sync Container Apps Job.

Uses a dedicated service principal with Contributor access to the
Container Apps Job resource to start job executions.
"""
import logging
from typing import Optional, Dict, Any

from azure.identity import ClientSecretCredential
from azure.mgmt.appcontainers import ContainerAppsAPIClient
from azure.mgmt.appcontainers.models import JobExecutionTemplate, JobExecutionContainer, EnvironmentVar
from azure.core.exceptions import AzureError

from shared_quickscribe_py.config import get_settings

logger = logging.getLogger(__name__)


class PlaudSyncTriggerError(Exception):
    """Exception raised when triggering the Plaud sync job fails."""
    pass


class PlaudSyncTrigger:
    """
    Service for triggering the Plaud Sync Container Apps Job.

    Uses Azure SDK with service principal authentication to start
    the job via the Azure Management API.
    """

    def __init__(self):
        """Initialize the trigger service with settings."""
        settings = get_settings()

        if not settings.plaud_sync_trigger_enabled:
            raise PlaudSyncTriggerError(
                "Plaud sync trigger is not enabled. "
                "Set PLAUD_SYNC_TRIGGER_ENABLED=true and configure the service principal."
            )

        if not settings.plaud_sync_trigger:
            raise PlaudSyncTriggerError(
                "Plaud sync trigger settings not configured. "
                "Check PLAUD_SYNC_TRIGGER_* environment variables."
            )

        self._settings = settings.plaud_sync_trigger
        self._client: Optional[ContainerAppsAPIClient] = None

    def _get_client(self) -> ContainerAppsAPIClient:
        """Get or create the Container Apps API client."""
        if self._client is None:
            credential = ClientSecretCredential(
                tenant_id=self._settings.tenant_id,
                client_id=self._settings.client_id,
                client_secret=self._settings.client_secret
            )
            self._client = ContainerAppsAPIClient(
                credential=credential,
                subscription_id=self._settings.subscription_id
            )
        return self._client

    def trigger_sync(self) -> Dict[str, Any]:
        """
        Trigger the Plaud Sync Container Apps Job.

        Returns:
            Dict containing execution details:
            - execution_name: Name of the started execution
            - job_name: Name of the job
            - resource_group: Resource group name
            - status: Initial status

        Raises:
            PlaudSyncTriggerError: If triggering fails
        """
        try:
            client = self._get_client()

            logger.info(
                f"Triggering Plaud sync job: {self._settings.job_name} "
                f"in resource group: {self._settings.resource_group}"
            )

            # Get the job definition to find the container image and name
            job = client.jobs.get(
                resource_group_name=self._settings.resource_group,
                job_name=self._settings.job_name
            )

            # Extract container config from job template
            container_name = self._settings.job_name
            container_image = None
            if job.template and job.template.containers:
                container_name = job.template.containers[0].name
                container_image = job.template.containers[0].image

            if not container_image:
                raise PlaudSyncTriggerError("Could not determine container image from job definition")

            logger.info(f"Using container: {container_name}, image: {container_image}")

            # Create execution template with TRIGGER_SOURCE=manual
            template = JobExecutionTemplate(
                containers=[
                    JobExecutionContainer(
                        name=container_name,
                        image=container_image,
                        env=[
                            EnvironmentVar(name="TRIGGER_SOURCE", value="manual")
                        ]
                    )
                ]
            )

            # Start the job - this returns an LROPoller
            poller = client.jobs.begin_start(
                resource_group_name=self._settings.resource_group,
                job_name=self._settings.job_name,
                template=template
            )

            # Get the initial result (the job execution)
            execution = poller.result()

            execution_name = getattr(execution, 'name', None)
            status = getattr(execution, 'status', 'started') if execution else 'triggered'

            logger.info(
                f"Plaud sync job triggered successfully. "
                f"Execution: {execution_name}, Status: {status}"
            )

            return {
                'execution_name': execution_name,
                'job_name': self._settings.job_name,
                'resource_group': self._settings.resource_group,
                'status': status
            }

        except AzureError as e:
            logger.error(f"Azure API error triggering Plaud sync job: {e}")
            raise PlaudSyncTriggerError(f"Failed to trigger Plaud sync job: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error triggering Plaud sync job: {e}")
            raise PlaudSyncTriggerError(f"Unexpected error: {e}") from e

    def get_job_status(self) -> Dict[str, Any]:
        """
        Get the current status of the Plaud Sync Job.

        Returns:
            Dict containing job status information
        """
        try:
            client = self._get_client()

            job = client.jobs.get(
                resource_group_name=self._settings.resource_group,
                job_name=self._settings.job_name
            )

            return {
                'job_name': job.name,
                'provisioning_state': job.provisioning_state,
                'trigger_type': getattr(job.configuration, 'trigger_type', None) if job.configuration else None,
            }

        except AzureError as e:
            logger.error(f"Azure API error getting job status: {e}")
            raise PlaudSyncTriggerError(f"Failed to get job status: {e}") from e


# Singleton instance (lazy initialization)
_trigger_instance: Optional[PlaudSyncTrigger] = None


def get_plaud_sync_trigger() -> PlaudSyncTrigger:
    """
    Get the PlaudSyncTrigger singleton instance.

    Returns:
        PlaudSyncTrigger instance

    Raises:
        PlaudSyncTriggerError: If the trigger is not configured
    """
    global _trigger_instance
    if _trigger_instance is None:
        _trigger_instance = PlaudSyncTrigger()
    return _trigger_instance


def trigger_plaud_sync() -> Dict[str, Any]:
    """
    Convenience function to trigger the Plaud sync job.

    Returns:
        Dict containing execution details

    Raises:
        PlaudSyncTriggerError: If triggering fails
    """
    trigger = get_plaud_sync_trigger()
    return trigger.trigger_sync()
