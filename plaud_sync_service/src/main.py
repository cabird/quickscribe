#!/usr/bin/env python3
"""
Entry point for QuickScribe Processing Service.
Runs Plaud sync + speaker identification without HTTP wrapper.
"""
import os
import sys
import logging
import warnings

# Suppress noisy torch/speechbrain FutureWarnings
warnings.filterwarnings("ignore", category=FutureWarning)

from shared_quickscribe_py.config import get_settings
from job_executor import JobExecutor
from service_version import SERVICE_VERSION

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress verbose Azure SDK logs
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)
logging.getLogger('azure').setLevel(logging.WARNING)


def main():
    """Execute the QuickScribe processing service."""
    logger.info("=" * 80)
    logger.info(f"Starting QuickScribe Processing Service (v{SERVICE_VERSION})")
    logger.info("=" * 80)

    try:
        settings = get_settings()
        logger.info(f"Configuration loaded (environment: {settings.environment})")

        trigger_source = os.getenv('TRIGGER_SOURCE', 'scheduled')
        test_run_id = os.getenv('TEST_RUN_ID')
        max_recordings_str = os.getenv('MAX_RECORDINGS')
        max_speaker_id_str = os.getenv('MAX_SPEAKER_ID_PER_USER')

        max_recordings = None
        if max_recordings_str:
            try:
                max_recordings = int(max_recordings_str)
                logger.info(f'MAX_RECORDINGS limit set to: {max_recordings}')
            except ValueError:
                logger.warning(f'Invalid MAX_RECORDINGS value: {max_recordings_str}, ignoring')

        if max_speaker_id_str:
            logger.info(f'MAX_SPEAKER_ID_PER_USER: {max_speaker_id_str}')

        if test_run_id:
            logger.info(f'Running in test mode with TEST_RUN_ID: {test_run_id}')

        executor = JobExecutor(settings)
        job_id = executor.execute_sync_job(
            trigger_source=trigger_source,
            user_id=None,
            test_run_id=test_run_id,
            max_recordings=max_recordings
        )

        logger.info("=" * 80)
        logger.info(f'Processing completed successfully: {job_id}')
        logger.info("=" * 80)
        sys.exit(0)

    except Exception as e:
        logger.error("=" * 80)
        logger.error(f'Processing failed with error: {str(e)}')
        import traceback
        logger.error(f'Stack trace:\n{traceback.format_exc()}')
        logger.error("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    main()
