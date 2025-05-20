"""
Centralized logging configuration for QuickScribe backend.
Provides Azure Application Insights integration and standardized logging.
"""

import os
import sys
import json
import logging
from datetime import datetime
from api_version import API_VERSION

#load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Define the application namespace for logging
APP_NAMESPACE_BASE = "quickscribe.backend"

# Import Azure Monitor OpenTelemetry integration
try:
    from opencensus.ext.azure.log_exporter import AzureLogHandler
    AZURE_LOGGING_AVAILABLE = True
    print("?? Azure logging available")
    logging.info("?? Azure logging available")
    print(f"?? APPLICATIONINSIGHTS_CONNECTION_STRING: {os.environ.get('APPLICATIONINSIGHTS_CONNECTION_STRING')}")
    logging.info(f"?? APPLICATIONINSIGHTS_CONNECTION_STRING: {os.environ.get('APPLICATIONINSIGHTS_CONNECTION_STRING')}")
    print(f"?? APPLICATIONINSIGHTS_USE_OPENCENSUS: {os.environ.get('APPLICATIONINSIGHTS_USE_OPENCENSUS')}")
    logging.info(f"?? APPLICATIONINSIGHTS_USE_OPENCENSUS: {os.environ.get('APPLICATIONINSIGHTS_USE_OPENCENSUS')}")
except ImportError:
    AZURE_LOGGING_AVAILABLE = False
    print("?? Azure logging not available, skipping AzureLogHandler import")
    logging.info("?? Azure logging not available, skipping AzureLogHandler import")


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
        if hasattr(record, 'route'):
            log_obj['route'] = record.route
        
        # If record has custom_dimensions (for App Insights), include them
        if hasattr(record, 'custom_dimensions'):
            for key, value in record.custom_dimensions.items():
                log_obj[key] = value
            
        return json.dumps(log_obj)


# Custom filter to move additional attributes into custom_dimensions
class MetadataFilter(logging.Filter):
    def __init__(self, service_name=APP_NAMESPACE_BASE, app_version="unknown", namespace="Unknown"):
        super().__init__()
        self.service_name = service_name
        self.app_version = app_version
        self.namespace = namespace
        
    def filter(self, record):
        # Initialize custom_dimensions if not present
        if not hasattr(record, 'custom_dimensions'):
            record.custom_dimensions = {}

        # Add standard metadata
        record.custom_dimensions['service'] = self.service_name
        record.custom_dimensions['app_namespace'] = self.namespace
        record.custom_dimensions['container_version'] = self.app_version
        
        # Add specific attributes to custom_dimensions if they exist
        for attr in ['recording_id', 'action', 'user_id', 'route', 'request_id']:
            if hasattr(record, attr):
                record.custom_dimensions[attr] = getattr(record, attr)
        
        return True  # Always include the record


def setup_logger(module_name, app_version=API_VERSION):
    """
    Configure and return a logger for the specified module.
    
    Args:
        module_name: The name of the module using this logger
        app_version: The version of the application
        
    Returns:
        A configured logger instance
    """
    # Create a logger name prefixed with the application namespace
    logger_name = f"{APP_NAMESPACE_BASE}.{module_name}"
    logger = logging.getLogger(logger_name)
    
    # If the logger is already configured, return it
    if logger.handlers:
        return logger
        
    logger.setLevel(logging.INFO)
    logger.propagate = False  # Don't propagate to root logger

    # Add the filter that will process metadata
    logger.addFilter(MetadataFilter(service_name=APP_NAMESPACE_BASE, app_version=app_version, namespace=logger_name))

    # Remove default handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create console handler with JSON formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(JSONFormatter())
    logger.addHandler(console_handler)
    
    # Set log level from environment
    log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
    logger.setLevel(getattr(logging, log_level, logging.INFO))
    
    # If App Insights connection string is available, add the AzureLogHandler
    if 'APPLICATIONINSIGHTS_CONNECTION_STRING' in os.environ:
        # Add Azure Application Insights handler
        azure_handler = AzureLogHandler(connection_string=os.environ['APPLICATIONINSIGHTS_CONNECTION_STRING'])
        azure_handler.setFormatter(logging.Formatter('%(message)s'))  # Use default formatter for Azure logs
        logger.addHandler(azure_handler)
    return logger

def get_logger(module_name, app_version=API_VERSION):
    """
    Get a context logger for a specific module with optional context data.
    
    Args:
        module_name: Name of the module (e.g., 'api', 'auth', etc.)
        app_version: The application version
        
    Returns:
        A tLogger instance
    """
    base_logger = setup_logger(module_name, app_version)
    return base_logger