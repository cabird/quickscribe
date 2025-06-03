import os
from opencensus.ext.azure.log_exporter import AzureLogHandler
from opencensus.ext.azure.metrics_exporter import MetricsExporter
from opencensus.stats import aggregation as aggregation_module
from opencensus.stats import measure as measure_module
from opencensus.stats import stats as stats_module
from opencensus.stats import view as view_module
from opencensus.tags import tag_map as tag_map_module
import logging
import time
import uuid
import random
from dotenv import load_dotenv
import copy

# Load environment variables from .env file
load_dotenv()

# Get Application Insights connection string
connection_string = os.getenv('APPLICATIONINSIGHTS_CONNECTION_STRING')

# Set up logging with Azure Log Handler
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Add Azure Log Handler
azure_log_handler = AzureLogHandler(connection_string=connection_string)
logger.addHandler(azure_log_handler)

# Set up console handler (to see logs locally)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
logger.addHandler(console_handler)

def main():
    # Generate a unique ID for this session
    session_id = str(uuid.uuid4())
    
    # Log a trace message
    logger.info(f"App insights test script started with session ID: {session_id}")
    
    # Log custom event with properties
    properties = {
        'session_id': session_id,
        'environment': 'development'
    }
    logger.info("Custom event example", extra={'custom_dimensions': properties})
    
    try:
        # Set up custom metrics
        stats = stats_module.stats
        view_manager = stats.view_manager
        stats_recorder = stats.stats_recorder
        
        # Create a measure for request processing time
        processing_time_measure = measure_module.MeasureFloat(
            "processing_time", "Time to process a request", "ms")
        
        # Create a view to track the processing time
        processing_time_view = view_module.View(
            "processing_time_view",
            "Processing time distribution",
            [],
            processing_time_measure,
            aggregation_module.LastValueAggregation())
        
        # Register the view
        view_manager.register_view(processing_time_view)
        
        # Create metrics exporter
        exporter = MetricsExporter(
            connection_string=connection_string)
        view_manager.register_exporter(exporter)
        
        # Record a few metrics
        for i in range(5):
            # Simulate processing time
            processing_time = random.uniform(100, 500)
            
            # Log an info message for each iteration
            logger.info(f"Processing iteration {i+1}, took {processing_time:.2f} ms",
                      extra={'custom_dimensions': {'iteration': i+1}})
            
            # Record metric using measurement map
            mmap = stats_recorder.new_measurement_map()
            tmap = tag_map_module.TagMap()
            mmap.measure_float_put(processing_time_measure, processing_time)
            mmap.record(tmap)
            
            # Send the metrics
            #exporter.export_metrics([exporter.get_metrics()[0]])
            
            # Sleep a bit to space out events
            time.sleep(1)
            
        # Simulate an error
        try:
            # Intentionally cause an exception
            result = 1 / 0
        except Exception as e:
            # Log the exception to App Insights
            logger.exception("Caught a division by zero error")
            
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {str(e)}")
    
    finally:
        # Log completion message
        logger.info(f"App insights test script completed with session ID: {session_id}")
        
        # Force a flush to ensure all telemetry is sent
        azure_log_handler.flush()


if __name__ == "__main__":
    main()
    # Sleep to allow time for telemetry to be sent
    time.sleep(5)
