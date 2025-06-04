import os
import time
import random
import logging
from dotenv import load_dotenv
from applicationinsights import TelemetryClient
from applicationinsights.logging import LoggingHandler

# Load environment variables
load_dotenv()

# Get Application Insights connection string
connection_string = os.getenv('APPLICATIONINSIGHTS_CONNECTION_STRING')

# Extract instrumentation key from connection string
if connection_string:
    # Find the instrumentation key in the connection string
    parts = connection_string.split(';')
    for part in parts:
        if part.startswith('InstrumentationKey='):
            instrumentation_key = part.split('=', 1)[1]
            break
else:
    raise ValueError("APPLICATIONINSIGHTS_CONNECTION_STRING not found in environment variables")

# Create a telemetry client
telemetry_client = TelemetryClient(instrumentation_key)

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Add Application Insights handler
ai_handler = LoggingHandler(instrumentation_key)
logger.addHandler(ai_handler)

# Add console handler for local viewing
console_handler = logging.StreamHandler()
logger.addHandler(console_handler)

def main():
    # Log information
    logger.info("Script started")
    
    # Track custom event
    telemetry_client.track_event("ScriptExecution", {"environment": "development"})
    
    # Track metrics
    for i in range(3):
        # Simulate some work
        value = random.uniform(1, 100)
        logger.info(f"Iteration {i+1}: Generated value {value:.2f}")
        
        # Track a metric
        telemetry_client.track_metric("RandomValue", value)
        
        # Track a custom event with properties
        telemetry_client.track_event(
            "IterationCompleted", 
            {"iteration": i+1, "status": "success"}
        )
        
        time.sleep(1)
    
    # Simulate error tracking
    try:
        # Intentionally cause an error
        result = 1 / 0
    except Exception as e:
        # Log the exception
        logger.exception("An error occurred")
        # Track the exception
        telemetry_client.track_exception()
    
    # Track request
    telemetry_client.track_request("SampleRequest", "http://example.com", True, 
                                  start_time="2023-01-01T12:00:00.000Z", 
                                  duration=1250,
                                  response_code=200, 
                                  http_method="GET")
    
    # Track dependency
    telemetry_client.track_dependency("database", "SQL", "SELECT * FROM table", 
                                     start_time="2023-01-01T12:00:00.000Z", 
                                     duration=123, 
                                     result_code=0, 
                                     success=True)
    
    # Log completion
    logger.info("Script completed")
    
    # Flush telemetry to ensure all data is sent
    telemetry_client.flush()

if __name__ == "__main__":
    main()
    # Allow time for telemetry to be sent
    time.sleep(3)
