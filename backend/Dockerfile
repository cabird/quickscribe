# Use the official Python image as a base
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy and install shared_quickscribe_py library (copied into temp dir by Makefile)
COPY shared_quickscribe_py /tmp/shared_quickscribe_py
RUN pip install -e /tmp/shared_quickscribe_py

# Copy project files
COPY . .

# Set Python path to include src directory
ENV PYTHONPATH=/app/src:$PYTHONPATH

# Azure expects the app to listen on 0.0.0.0 and $PORT
ENV PORT=8000

# Expose the port
EXPOSE 8000

# Copy startup script
COPY startup.sh /app/startup.sh
RUN chmod +x /app/startup.sh
ENTRYPOINT ["/app/startup.sh"]
