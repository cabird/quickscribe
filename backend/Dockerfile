# Use the official Python image as a base
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Azure expects the app to listen on 0.0.0.0 and $PORT
ENV PORT=8000

# Expose the port
EXPOSE 8000

# Copy startup script
COPY startup.sh /app/startup.sh
RUN chmod +x /app/startup.sh
ENTRYPOINT ["/app/startup.sh"]
