"""
Logging setup for the transcoder container.
Configures structured logging with JSON formatting and Azure Application Insights integration.
"""

import os
import sys
import json
import logging
from datetime import datetime
from opencensus.ext.azure.log_exporter import AzureLogHandler
from container_app_version import CONTAINER_APP_VERSION

# A dictionary to store loggers by context
context_loggers = {}

def setup_azure_logging(app_namespace="quickscribe.transcoder"):
    """Configure logging optimized for Azure Container Apps/Instances with Application Insights integration"""
    
    # Create custom formatter with JSON output for structured logs
    class JSONFormatter(logging.Formatter):
        def format(self, record):
            log_obj = {
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'level': record.levelname,
                'logger': record.name,
                'message': record.getMessage(),
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno
            }
            
            # Add extra fields if present
            if hasattr(record, 'recording_id'):
                log_obj['recording_id'] = record.recording_id
            if hasattr(record, 'action'):
                log_obj['action'] = record.action
            if hasattr(record, 'user_id'):
                log_obj['user_id'] = record.user_id
            
            # If record has custom_dimensions (for App Insights), include them
            if hasattr(record, 'custom_dimensions'):
                for key, value in record.custom_dimensions.items():
                    log_obj[key] = value
                
            return json.dumps(log_obj)
        
    # Custom filter to move additional attributes into custom_dimensions
    class MetadataFilter(logging.Filter):
        def filter(self, record):
            # Initialize custom_dimensions if not present
            if not hasattr(record, 'custom_dimensions'):
                record.custom_dimensions = {}

            record.custom_dimensions['service'] = "quickscribe"
            record.custom_dimensions['app_namespace'] = app_namespace
            record.custom_dimensions['container_version'] = CONTAINER_APP_VERSION
            
            # Add specific attributes to custom_dimensions if they exist
            for attr in ['recording_id', 'action', 'user_id']:
                if hasattr(record, attr):
                    record.custom_dimensions[attr] = getattr(record, attr)
                    # Optionally: remove from record to prevent it from appearing in other formatters
                    # delattr(record, attr)
            
            return True  # Always include the record
    
    # Configure app logger (not root logger, to avoid SDK logs)
    logger = logging.getLogger(app_namespace)
    logger.setLevel(logging.INFO)
    logger.propagate = False  # Don't propagate to root logger

    # Add the filter that will process metadata
    logger.addFilter(MetadataFilter())
    
    # Remove default handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create console handler with JSON formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(JSONFormatter())
    logger.addHandler(console_handler)
    
    # Set Azure-specific log level from environment
    log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
    logger.setLevel(getattr(logging, log_level, logging.INFO))
    
    # If App Insights connection string is available but we're using the older SDK approach
    # as a fallback, add the AzureLogHandler explicitly
    if 'APPLICATIONINSIGHTS_CONNECTION_STRING' in os.environ:        
        # Add Azure Application Insights handler
        azure_handler = AzureLogHandler(
            connection_string=os.environ.get('APPLICATIONINSIGHTS_CONNECTION_STRING')
        )

        azure_handler.setFormatter(logging.Formatter('%(message)s'))  # Use default formatter for Azure logs
        logger.addHandler(azure_handler)
    
    return logger


def get_context_logger(base_logger, context=None):
    """
    Get a logger that includes context information such as recording_id, user_id, etc.
    If no context is provided, returns the base logger.
    
    Args:
        base_logger: The base logger to use
        context: Dictionary with context info like recording_id, user_id, etc.
    
    Returns:
        A LoggerAdapter that includes the provided context in all log messages.
    """
    if not context:
        return base_logger
    
    # Create a key for this context
    context_key = "|".join([f"{k}:{v}" for k, v in sorted(context.items())])
    
    # If we already have a logger for this context, return it
    if context_key in context_loggers:
        return context_loggers[context_key]
    
    # Create a LoggerAdapter that adds context to each log record
    class ContextAdapter(logging.LoggerAdapter):
        def process(self, msg, kwargs):
            # First, ensure we have an extra dict
            if 'extra' not in kwargs:
                kwargs['extra'] = {}
            
            # Add all context items to the extra dict
            for key, value in self.extra.items():
                if key not in kwargs['extra']:
                    kwargs['extra'][key] = value
            
            return msg, kwargs
    
    # Create and store the adapter
    adapter = ContextAdapter(base_logger, context)
    context_loggers[context_key] = adapter
    
    return adapter
