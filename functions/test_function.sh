#!/bin/bash

# URL of the local function
FUNCTION_URL="http://localhost:7071/api/QuickScribeTranscription"

# Data to send in the request
DATA='{"name": "John"}'

# Sending POST request to the function
echo "Sending request to Azure Function..."

RESPONSE=$(curl -s -X POST "$FUNCTION_URL" \
    -H "Content-Type: application/json" \
    -d "$DATA")

# Check if the request was successful
if [ $? -ne 0 ]; then
    echo "Failed to connect to the function."
    exit 1
fi

# Print the response from the function
echo "Response from function:"
echo "$RESPONSE"

