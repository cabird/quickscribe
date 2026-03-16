#!/usr/bin/env python3
"""
Entry point for Speaker Identification Service.
Runs the speaker identification process directly without HTTP wrapper.
"""
import os
import sys
import logging

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
    """Execute the speaker identification service."""
    logger.info("=" * 80)
    logger.info(f"Starting Speaker Identification Service (v{SERVICE_VERSION})")
    logger.info("=" * 80)

    try:
        # Load and validate configuration
        settings = get_settings()
        logger.info(f"Configuration loaded (environment: {settings.environment})")

        # Get execution parameters from environment
        max_recordings_str = os.getenv('MAX_RECORDINGS')

        max_recordings = None
        if max_recordings_str:
            try:
                max_recordings = int(max_recordings_str)
                logger.info(f'MAX_RECORDINGS limit set to: {max_recordings}')
            except ValueError:
                logger.warning(f'Invalid MAX_RECORDINGS value: {max_recordings_str}, ignoring')

        # Execute identification
        executor = JobExecutor(settings)
        job_id = executor.execute_identification_job(
            max_recordings=max_recordings
        )

        logger.info("=" * 80)
        logger.info(f'Speaker identification completed successfully: {job_id}')
        logger.info("=" * 80)
        sys.exit(0)

    except Exception as e:
        logger.error("=" * 80)
        logger.error(f'Speaker identification failed with error: {str(e)}')
        import traceback
        logger.error(f'Stack trace:\n{traceback.format_exc()}')
        logger.error("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    main()
