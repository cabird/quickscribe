"""
Azure Functions app for Plaud Sync Service.
Defines timer and HTTP triggers for job execution.
"""
import azure.functions as func
import logging
import json
import os
import sys

from shared_quickscribe_py.config import get_settings
from job_executor import JobExecutor
from service_version import SERVICE_VERSION

# Configure logging - suppress verbose Azure SDK HTTP logs
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)
logging.getLogger('azure').setLevel(logging.WARNING)

# Load and validate configuration at startup
try:
    settings = get_settings()
    logging.info(f"Configuration loaded successfully (environment: {settings.environment})")
except SystemExit as e:
    logging.critical("Configuration validation failed - service cannot start")
    sys.exit(1)

# Create the Functions app
app = func.FunctionApp()


@app.timer_trigger(schedule="0 */15 * * * *", arg_name="timer", run_on_startup=False)
def scheduled_sync(timer: func.TimerRequest) -> None:
    """
    Timer trigger that runs every 15 minutes.
    Processes all users with Plaud sync enabled.
    """
    logging.info('=== Scheduled Plaud Sync Trigger ===')

    if timer.past_due:
        logging.info('Timer is past due!')

    try:
        # Check for TEST_RUN_ID environment variable (for testing in test environments)
        test_run_id = os.getenv('TEST_RUN_ID')
        if test_run_id:
            logging.info(f'Running in test mode with TEST_RUN_ID: {test_run_id}')

        # Read MAX_RECORDINGS from environment (for testing/limiting)
        max_recordings = os.getenv('MAX_RECORDINGS')
        if max_recordings:
            try:
                max_recordings = int(max_recordings)
                logging.info(f'MAX_RECORDINGS limit set to: {max_recordings}')
            except ValueError:
                logging.warning(f'Invalid MAX_RECORDINGS value: {max_recordings}, ignoring')
                max_recordings = None
        else:
            max_recordings = None

        executor = JobExecutor(settings)
        job_id = executor.execute_sync_job(
            trigger_source="scheduled",
            user_id=None,
            test_run_id=test_run_id,
            max_recordings=max_recordings
        )
        logging.info(f'Job execution started: {job_id}')

    except Exception as e:
        logging.error(f'Error in scheduled sync: {str(e)}')
        import traceback
        logging.error(f'Stack trace: {traceback.format_exc()}')


@app.route(route="sync/trigger", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def manual_sync(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP trigger for manual job execution.
    Can be called from backend or directly for testing.
    """
    logging.info('=== Manual Plaud Sync Trigger ===')

    try:
        # Get user_id and testRunId from request body or query params
        user_id = req.params.get('user_id')
        test_run_id = req.params.get('testRunId')

        if not user_id or not test_run_id:
            try:
                req_body = req.get_json()
                if not user_id:
                    user_id = req_body.get('user_id')
                if not test_run_id:
                    test_run_id = req_body.get('testRunId')
            except:
                pass  # No JSON body provided

        # Read MAX_RECORDINGS from environment (for testing/limiting)
        max_recordings = os.getenv('MAX_RECORDINGS')
        if max_recordings:
            try:
                max_recordings = int(max_recordings)
                logging.info(f'MAX_RECORDINGS limit set to: {max_recordings}')
            except ValueError:
                logging.warning(f'Invalid MAX_RECORDINGS value: {max_recordings}, ignoring')
                max_recordings = None
        else:
            max_recordings = None

        # Execute sync job
        executor = JobExecutor(settings)
        job_id = executor.execute_sync_job(
            trigger_source="manual",
            user_id=user_id,
            test_run_id=test_run_id,
            max_recordings=max_recordings
        )

        return func.HttpResponse(
            body=json.dumps({"job_id": job_id, "status": "started"}),
            status_code=202,  # Accepted
            mimetype="application/json"
        )

    except Exception as e:
        logging.error(f'Error in manual sync: {str(e)}')
        import traceback
        logging.error(f'Stack trace: {traceback.format_exc()}')

        return func.HttpResponse(
            body=json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )


@app.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint."""
    response_data = {
        "status": "healthy",
        "service": "plaud_sync_service",
        "version": SERVICE_VERSION
    }
    return func.HttpResponse(
        body=json.dumps(response_data),
        status_code=200,
        mimetype="application/json"
    )
